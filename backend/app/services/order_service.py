from __future__ import annotations

import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.connectors.base import NormalizedOrder
from app.core.timeutils import local_now
from app.models.catalog import OptionPricingMode, Product, ProductIngredient, ProductOption, ProductOptionGroup, SalesChannel
from app.models.establishment import Establishment
from app.models.delivery import Courier, DeliveryZone
from app.models.order import FulfillmentType, Order, OrderEvent, OrderItem, OrderSource, OrderStatus, PaymentStatus
from app.schemas.order import LocalOrderCreate, OrderItemCreate, OrderItemOptionCreate
from app.services import customer_service, stock_service
from app.services.availability import channel_for_source, missing_ingredient_names, option_is_available, product_block_reason

MISSING_GROUP_NAME = "Em falta"

ACTIVE_STATUSES = {OrderStatus.NEW, OrderStatus.ACCEPTED, OrderStatus.PREPARING, OrderStatus.READY, OrderStatus.OUT_FOR_DELIVERY}
TERMINAL_STATUSES = {OrderStatus.FINISHED, OrderStatus.CANCELED}

ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.NEW: {OrderStatus.ACCEPTED, OrderStatus.CANCELED},
    OrderStatus.ACCEPTED: {OrderStatus.PREPARING, OrderStatus.CANCELED},
    OrderStatus.PREPARING: {OrderStatus.READY, OrderStatus.CANCELED},
    OrderStatus.READY: {OrderStatus.OUT_FOR_DELIVERY, OrderStatus.FINISHED, OrderStatus.CANCELED},
    OrderStatus.OUT_FOR_DELIVERY: {OrderStatus.FINISHED, OrderStatus.CANCELED},
    OrderStatus.FINISHED: set(),
    OrderStatus.CANCELED: set(),
}

MAX_ORDER_NUMBER_ATTEMPTS = 5


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


def unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=422, detail=detail)


def generate_order_number(db: Session, establishment_id: str) -> str:
    """Sequencia diaria por loja, no fuso da loja: CH-AAMMDD-0001, CH-AAMMDD-0002...

    Usa o maior numero ja emitido com o prefixo do dia (e nao a contagem de pedidos)
    para nao repetir numeros quando pedidos sao importados com datas retroativas.
    """
    tz_name = db.scalar(select(Establishment.timezone).where(Establishment.id == establishment_id))
    prefix = f"CH-{local_now(tz_name).strftime('%y%m%d')}-"
    numbers = db.scalars(
        select(Order.order_number).where(Order.establishment_id == establishment_id, Order.order_number.like(f"{prefix}%"))
    ).all()
    suffixes = [number.rsplit("-", 1)[-1] for number in numbers]
    last = max((int(suffix) for suffix in suffixes if suffix.isdigit()), default=0)
    return f"{prefix}{last + 1:04d}"


def source_for_local_fulfillment(fulfillment_type: FulfillmentType) -> OrderSource:
    if fulfillment_type == FulfillmentType.COUNTER:
        return OrderSource.COUNTER
    if fulfillment_type == FulfillmentType.PICKUP:
        return OrderSource.STORE_PICKUP
    return OrderSource.OWN_DELIVERY


def add_event(
    db: Session,
    order: Order,
    event_type: str,
    previous_status: OrderStatus | None,
    new_status: OrderStatus | None,
    payload: dict | None = None,
) -> None:
    db.add(
        OrderEvent(
            order=order,
            event_type=event_type,
            previous_status=previous_status,
            new_status=new_status,
            payload=payload or {},
            created_at=now_utc(),
        )
    )


def _load_available_products(
    db: Session, establishment_id: str, lines: Iterable[OrderItemCreate], channel: SalesChannel | None
) -> dict[str, Product]:
    product_ids = {line.product_id for line in lines}
    products = db.scalars(
        select(Product)
        .where(Product.establishment_id == establishment_id, Product.id.in_(product_ids))
        .options(
            selectinload(Product.option_groups)
            .selectinload(ProductOptionGroup.options)
            .selectinload(ProductOption.linked_product)
            .selectinload(Product.ingredient_links),
            selectinload(Product.ingredient_links).selectinload(ProductIngredient.ingredient),
        )
    ).all()
    found = {product.id: product for product in products}
    if product_ids - set(found):
        raise unprocessable("Produto indisponivel ou inexistente")
    for product in products:
        reason = product_block_reason(product, channel)
        if reason:
            raise unprocessable(f"Produto indisponivel: {reason}")
    return found


@dataclass(frozen=True)
class ResolvedChoice:
    group: ProductOptionGroup
    option: ProductOption
    quantity: int
    notes: str | None

    def snapshot(self) -> dict:
        """Retrato gravado no item: o pedido continua legivel mesmo se o cardapio mudar depois."""
        return {
            "option_id": self.option.id,
            "group_id": self.group.id,
            "group_name": self.group.name,
            "pricing_mode": OptionPricingMode(self.group.pricing_mode).value,
            "name": self.option.name,
            "price_delta": str(money(self.option.price_delta)),
            "quantity": self.quantity,
            "notes": self.notes,
        }


def resolve_line_options(
    product: Product, selections: list[OrderItemOptionCreate], channel: SalesChannel | None = None
) -> list[ResolvedChoice]:
    """Valida as escolhas contra os grupos do proprio produto.

    Confere pertencimento, disponibilidade no canal, repeticao e minimo/maximo por grupo (contando
    unidades). Grupos condicionais (ex.: bebida do combo) so valem quando a opcao que os libera
    foi escolhida. Escolhas repetidas da mesma opcao sao somadas. Retorna na ordem do cardapio.
    """
    position: dict[str, int] = {}
    options_by_id: dict[str, tuple[ProductOptionGroup, ProductOption]] = {}
    for group in product.option_groups:
        for option in group.options:
            position[option.id] = len(position)
            options_by_id[option.id] = (group, option)

    merged: dict[str, ResolvedChoice] = {}
    for selection in selections:
        if selection.option_id not in options_by_id:
            raise unprocessable(f"Complemento invalido para {product.name}")
        group, option = options_by_id[selection.option_id]
        if not option_is_available(option, channel):
            raise unprocessable(f"Complemento indisponivel: {option.name}")
        notes = (selection.notes or "").strip() or None
        quantity = selection.quantity
        previous = merged.get(option.id)
        if previous:
            quantity += previous.quantity
            notes = "; ".join(note for note in (previous.notes, notes) if note) or None
        merged[option.id] = ResolvedChoice(group=group, option=option, quantity=quantity, notes=notes)

    per_group: Counter[str] = Counter()
    for choice in merged.values():
        if choice.quantity > 1 and not choice.group.allow_repeat:
            raise unprocessable(f"{choice.option.name} so pode ser escolhido uma vez em {choice.group.name}")
        per_group[choice.group.id] += choice.quantity

    option_names = {option_id: option.name for option_id, (_group, option) in options_by_id.items()}
    active_groups: set[str] = set()
    for group in product.option_groups:
        count = per_group.get(group.id, 0)
        trigger = group.depends_on_option_id
        if trigger and not (trigger in merged and merged[trigger].group.id in active_groups):
            if count:
                raise unprocessable(f"{group.name} so pode ser escolhido junto com {option_names.get(trigger, 'a opcao que o libera')}")
            continue
        active_groups.add(group.id)
        if count < group.min_choices:
            raise unprocessable(f"Escolha pelo menos {group.min_choices} opcao(oes) em {group.name} para {product.name}")
        if group.max_choices and count > group.max_choices:
            raise unprocessable(f"Maximo de {group.max_choices} opcao(oes) em {group.name} para {product.name}")
    return sorted(merged.values(), key=lambda choice: position[choice.option.id])


def options_price(choices: list[ResolvedChoice]) -> Decimal:
    """Preco das escolhas, aplicando a regra de cada grupo (soma, mais cara ou media)."""
    by_group: dict[str, list[ResolvedChoice]] = defaultdict(list)
    for choice in choices:
        by_group[choice.group.id].append(choice)

    total = Decimal("0.00")
    for group_choices in by_group.values():
        mode = OptionPricingMode(group_choices[0].group.pricing_mode)
        if mode == OptionPricingMode.MAX:
            total += max(choice.option.price_delta for choice in group_choices)
        elif mode == OptionPricingMode.AVERAGE:
            units = sum(choice.quantity for choice in group_choices)
            weighted = sum((choice.option.price_delta * choice.quantity for choice in group_choices), Decimal("0.00"))
            total += (weighted / units).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            total += sum((choice.option.price_delta * choice.quantity for choice in group_choices), Decimal("0.00"))
    return total


def missing_snapshots(product: Product, chosen: list[ResolvedChoice], channel: SalesChannel | None) -> list[dict]:
    """Ingredientes em falta viram "Sem alface" no item, para a cozinha saber que vai sem."""
    chosen_names = {choice.option.name.strip().lower() for choice in chosen}
    snapshots = []
    for name in missing_ingredient_names(product, channel):
        label = f"Sem {name}"
        if label.lower() in chosen_names:
            continue
        snapshots.append({
            "option_id": None,
            "group_id": None,
            "group_name": MISSING_GROUP_NAME,
            "pricing_mode": OptionPricingMode.SUM.value,
            "name": label,
            "price_delta": "0.00",
            "quantity": 1,
            "notes": None,
        })
    return snapshots


def base_price(product: Product, channel: SalesChannel | None) -> Decimal:
    """Preco do item no canal (ex.: mais caro no iFood); sem preco do canal, vale o preco normal."""
    if channel is not None:
        value = (product.channel_prices or {}).get(SalesChannel(channel).value)
        if value is not None:
            return money(value)
    return money(product.price)


def quote_lines(
    db: Session, establishment_id: str, lines: list[OrderItemCreate], channel: SalesChannel | None = None
) -> tuple[list[tuple], Decimal]:
    """Calcula precos no servidor. Retorna as linhas precificadas e o subtotal."""
    if not lines:
        raise unprocessable("O pedido precisa de pelo menos um item")
    products = _load_available_products(db, establishment_id, lines, channel)
    priced_lines = []
    subtotal = Decimal("0.00")
    for line in lines:
        product = products[line.product_id]
        selected = resolve_line_options(product, line.all_selections(), channel)
        unit_price = money(base_price(product, channel) + options_price(selected))
        item_total = money(unit_price * line.quantity)
        subtotal += item_total
        usage = stock_service.line_usage(product, selected, channel)
        unit_cost = stock_service.usage_cost(db, usage)
        priced_lines.append((line, product, selected, unit_price, item_total, usage, unit_cost))
    return priced_lines, money(subtotal)


def create_order(
    db: Session,
    establishment_id: str,
    *,
    source: OrderSource,
    external_order_id: str | None,
    customer_name: str | None,
    customer_phone: str | None,
    delivery_address: str | None,
    fulfillment_type: FulfillmentType,
    payment_method,
    payment_status: PaymentStatus,
    delivery_fee: Decimal,
    discount: Decimal,
    notes: str | None,
    lines: list[OrderItemCreate],
    raw_payload: dict | None = None,
) -> Order:
    delivery_fee = money(delivery_fee)
    discount = money(discount)
    if delivery_fee < 0 or discount < 0:
        raise unprocessable("Taxa de entrega e desconto nao podem ser negativos")

    channel = channel_for_source(source)
    priced_lines, subtotal = quote_lines(db, establishment_id, lines, channel)
    if discount > subtotal:
        raise unprocessable("Desconto maior que o subtotal do pedido")

    for _attempt in range(MAX_ORDER_NUMBER_ATTEMPTS):
        order = Order(
            establishment_id=establishment_id,
            source=source,
            external_order_id=external_order_id,
            order_number=generate_order_number(db, establishment_id),
            customer_name=customer_name,
            customer_phone=customer_phone,
            delivery_address=delivery_address,
            fulfillment_type=fulfillment_type,
            payment_method=payment_method,
            payment_status=payment_status,
            status=OrderStatus.NEW,
            subtotal=subtotal,
            discount=discount,
            delivery_fee=delivery_fee,
            total=money(subtotal - discount + delivery_fee),
            notes=notes,
        )
        db.add(order)
        db.flush()
        order_usage: dict[str, Decimal] = defaultdict(Decimal)
        for line, product, selected, unit_price, item_total, usage, unit_cost in priced_lines:
            for ingredient_id, quantity in usage.items():
                order_usage[ingredient_id] += quantity * line.quantity
            db.add(
                OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    product_name=product.name,
                    quantity=line.quantity,
                    unit_price=unit_price,
                    total=item_total,
                    notes=line.notes,
                    selected_options=[choice.snapshot() for choice in selected] + missing_snapshots(product, selected, channel),
                    unit_cost=unit_cost,
                )
            )
        stock_service.consume_for_order(db, establishment_id, order.id, dict(order_usage))
        add_event(db, order, "ORDER_CREATED", None, OrderStatus.NEW, {"source": source.value, "raw_payload": raw_payload or {}})
        try:
            db.commit()
            return get_order_or_404(db, establishment_id, order.id)
        except IntegrityError:
            db.rollback()
            if external_order_id:
                existing = db.scalar(
                    select(Order).where(
                        Order.establishment_id == establishment_id,
                        Order.source == source,
                        Order.external_order_id == external_order_id,
                    )
                )
                if existing:
                    return get_order_or_404(db, establishment_id, existing.id)
            # Senao foi colisao de numero (dois pedidos no mesmo instante): tenta o proximo numero.
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Nao foi possivel gerar o numero do pedido, tente novamente")


def local_discount(db: Session, establishment: Establishment, payload: LocalOrderCreate, source: OrderSource):
    """Desconto manual + cupom + fidelidade (so validacao: nada e gravado aqui)."""
    _lines, subtotal = quote_lines(db, establishment.id, payload.items, channel_for_source(source))
    manual = money(payload.discount)
    promo = Decimal("0.00")
    coupon = None
    if payload.coupon_code and payload.coupon_code.strip():
        coupon, coupon_value = customer_service.check_coupon(db, establishment.id, payload.coupon_code, subtotal)
        promo += coupon_value
    customer = customer_service.find_by_phone(db, establishment.id, payload.customer_phone)
    if payload.use_loyalty_reward:
        promo += customer_service.check_reward(establishment, customer)
    # Cupom + fidelidade nunca deixam o pedido negativo; desconto manual maior que o pedido continua sendo recusado
    promo = max(Decimal("0.00"), min(promo, subtotal - manual))
    return manual + promo, coupon


def create_local_order(db: Session, establishment_id: str, payload: LocalOrderCreate,
                       source: OrderSource | None = None, raw_payload: dict | None = None,
                       neighborhood: str | None = None, trusted_customer_data: bool = True) -> Order:
    establishment = db.get(Establishment, establishment_id)
    source = source or source_for_local_fulfillment(payload.fulfillment_type)
    delivery_fee = payload.delivery_fee
    zone = None
    if payload.delivery_zone_id and payload.fulfillment_type == FulfillmentType.DELIVERY:
        zone = db.scalar(select(DeliveryZone).where(DeliveryZone.id == payload.delivery_zone_id, DeliveryZone.establishment_id == establishment_id))
        if zone is None or not zone.active:
            raise unprocessable("Bairro nao atendido")
        if "delivery_fee" not in payload.model_fields_set:
            delivery_fee = zone.fee
        neighborhood = neighborhood or zone.name
    discount, coupon = local_discount(db, establishment, payload, source)
    order = create_order(
        db,
        establishment_id,
        source=source,
        external_order_id=f"LOCAL-{uuid4().hex[:12].upper()}",
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        delivery_address=payload.delivery_address,
        fulfillment_type=payload.fulfillment_type,
        payment_method=payload.payment_method,
        payment_status=payload.payment_status,
        delivery_fee=delivery_fee,
        discount=discount,
        notes=payload.notes,
        lines=payload.items,
        raw_payload=raw_payload or {"mode": "local"},
    )
    customer = customer_service.upsert_from_order(
        db, establishment_id, payload.customer_phone, payload.customer_name, payload.delivery_address, neighborhood,
        overwrite=trusted_customer_data,
    )
    customer_service.register_order(db, establishment, order, customer, coupon, payload.use_loyalty_reward)
    order.delivery_zone_id = zone.id if zone else None
    order.neighborhood = neighborhood
    db.commit()
    return get_order_or_404(db, establishment_id, order.id)


def create_external_order(db: Session, establishment_id: str, normalized: NormalizedOrder) -> Order:
    existing = db.scalar(
        select(Order).where(
            Order.establishment_id == establishment_id,
            Order.source == normalized.source,
            Order.external_order_id == normalized.external_order_id,
        )
    )
    if existing:
        return get_order_or_404(db, establishment_id, existing.id)

    lines = [
        OrderItemCreate(
            product_id=item.product_id,
            quantity=item.quantity,
            option_ids=item.option_ids,
            notes=item.notes,
        )
        for item in normalized.items
    ]
    return create_order(
        db,
        establishment_id,
        source=normalized.source,
        external_order_id=normalized.external_order_id,
        customer_name=normalized.customer_name,
        customer_phone=normalized.customer_phone,
        delivery_address=normalized.delivery_address,
        fulfillment_type=normalized.fulfillment_type,
        payment_method=normalized.payment_method,
        payment_status=normalized.payment_status,
        delivery_fee=normalized.delivery_fee,
        discount=normalized.discount,
        notes=normalized.notes,
        lines=lines,
        raw_payload=normalized.raw_payload,
    )


def get_order_or_404(db: Session, establishment_id: str, order_id: str) -> Order:
    order = db.scalar(
        select(Order)
        .where(Order.id == order_id, Order.establishment_id == establishment_id)
        .options(selectinload(Order.items), selectinload(Order.events))
        .execution_options(populate_existing=True)
    )
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido nao encontrado")
    return order


def validate_transition(order: Order, new_status: OrderStatus, cancel_reason: str | None) -> None:
    if new_status == order.status:
        return
    if new_status not in ALLOWED_TRANSITIONS[order.status]:
        raise unprocessable(f"Transicao invalida: {order.status.value} para {new_status.value}")
    if new_status == OrderStatus.CANCELED and not (cancel_reason or "").strip():
        raise unprocessable("Informe o motivo do cancelamento")
    if order.marketplace_delivery:
        # Entregador do iFood retira na loja: a loja so deixa pronto
        if new_status == OrderStatus.OUT_FOR_DELIVERY:
            raise unprocessable("A entrega deste pedido e feita pelo entregador do iFood")
        return
    if order.fulfillment_type == FulfillmentType.DELIVERY and order.status == OrderStatus.READY and new_status == OrderStatus.FINISHED:
        raise unprocessable("Pedidos delivery precisam sair para entrega antes de finalizar")


def assign_courier(db: Session, establishment_id: str, order: Order, courier_id: str | None) -> None:
    if courier_id is None:
        order.courier_id = None
        return
    courier = db.scalar(select(Courier).where(Courier.id == courier_id, Courier.establishment_id == establishment_id))
    if courier is None or not courier.active:
        raise unprocessable("Motoboy invalido")
    order.courier_id = courier.id


def update_order_status(db: Session, establishment_id: str, order_id: str, new_status: OrderStatus,
                        cancel_reason: str | None = None, courier_id: str | None = None,
                        cancel_code: str | None = None) -> Order:
    order = get_order_or_404(db, establishment_id, order_id)
    validate_transition(order, new_status, cancel_reason)
    if new_status == OrderStatus.OUT_FOR_DELIVERY and courier_id:
        assign_courier(db, establishment_id, order, courier_id)
    if new_status == order.status:
        return order
    if order.integration == "IFOOD":
        from app.integrations.ifood import service as ifood_service

        # Avisa o iFood antes de mudar aqui. Cancelamento so vale quando o iFood confirmar (evento CAN).
        if ifood_service.push_status(db, order, new_status, cancel_code, cancel_reason):
            db.commit()
            return get_order_or_404(db, establishment_id, order_id)

    previous = order.status
    order.status = new_status
    if new_status == OrderStatus.CANCELED:
        stock_service.return_for_order(db, order.id)
        customer_service.revert_order(db, order)
    elif new_status == OrderStatus.FINISHED:
        customer_service.award_loyalty_point(db, order)
    add_event(
        db,
        order,
        "ORDER_STATUS_CHANGED",
        previous,
        new_status,
        {"cancel_reason": cancel_reason} if cancel_reason else {},
    )
    db.commit()
    return get_order_or_404(db, establishment_id, order_id)


def update_payment_status(db: Session, establishment_id: str, order_id: str, payment_status: PaymentStatus) -> Order:
    order = get_order_or_404(db, establishment_id, order_id)
    if order.payment_status == payment_status:
        return order
    previous = order.payment_status
    order.payment_status = payment_status
    add_event(db, order, "PAYMENT_STATUS_CHANGED", None, None, {"from": previous.value, "to": payment_status.value})
    db.commit()
    return get_order_or_404(db, establishment_id, order_id)


# ------------------------------------------------------------------ pedidos reais de marketplace (iFood)

STATUS_RANK = {
    OrderStatus.NEW: 0,
    OrderStatus.ACCEPTED: 1,
    OrderStatus.PREPARING: 2,
    OrderStatus.READY: 3,
    OrderStatus.OUT_FOR_DELIVERY: 4,
    OrderStatus.FINISHED: 5,
}


def _normalize_name(value: str | None) -> str:
    ascii_text = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    return " ".join(ascii_text.lower().split())


@dataclass(frozen=True)
class _Choice:
    option: ProductOption
    quantity: int


def _catalog_index(db: Session, establishment_id: str) -> tuple[dict[str, Product], dict[str, Product]]:
    products = db.scalars(
        select(Product)
        .where(Product.establishment_id == establishment_id)
        .options(
            selectinload(Product.option_groups).selectinload(ProductOptionGroup.options),
            selectinload(Product.ingredient_links).selectinload(ProductIngredient.ingredient),
        )
    ).all()
    return {product.id: product for product in products}, {_normalize_name(product.name): product for product in products}


def _match_option(product: Product, external_code: str | None, name: str) -> ProductOption | None:
    wanted = _normalize_name(name)
    for group in product.option_groups:
        for option in group.options:
            if (external_code and option.id == external_code) or _normalize_name(option.name) == wanted:
                return option
    return None


def create_marketplace_order(db: Session, establishment_id: str, data, source: OrderSource, integration: str,
                             raw_payload: dict | None = None) -> Order:
    """Pedido real vindo do marketplace: grava com os precos que o cliente pagou la (nao recalcula).

    Cada item e ligado ao produto do cardapio pelo codigo externo (= id do produto no ComandaHub) ou pelo
    nome. Itens ligados dao baixa no estoque e guardam o custo; os demais entram so com nome e preco.
    """
    existing = db.scalar(
        select(Order).where(Order.establishment_id == establishment_id, Order.source == source, Order.external_order_id == data.external_id)
    )
    if existing:
        return get_order_or_404(db, establishment_id, existing.id)

    by_id, by_name = _catalog_index(db, establishment_id)
    channel = channel_for_source(source)
    lines = []
    for item in data.items:
        product = by_id.get(item.external_code or "") or by_name.get(_normalize_name(item.name))
        snapshots, choices = [], []
        for option in item.options:
            matched = _match_option(product, option.external_code, option.name) if product else None
            if matched:
                choices.append(_Choice(matched, option.quantity))
            snapshots.append({
                "option_id": matched.id if matched else None,
                "group_id": matched.group_id if matched else None,
                "group_name": option.group_name or (matched.group.name if matched else "Complementos"),
                "pricing_mode": OptionPricingMode.SUM.value,
                "name": option.name,
                "price_delta": str(money(option.unit_price)),
                "quantity": option.quantity,
                "notes": None,
            })
        usage = stock_service.line_usage(product, choices, channel) if product else {}
        unit_cost = stock_service.usage_cost(db, usage) if product else None
        lines.append((item, product, snapshots, usage, unit_cost))

    for _attempt in range(MAX_ORDER_NUMBER_ATTEMPTS):
        order = Order(
            establishment_id=establishment_id,
            source=source,
            external_order_id=data.external_id,
            external_display_id=data.display_id,
            integration=integration,
            marketplace_delivery=data.marketplace_delivery,
            order_number=generate_order_number(db, establishment_id),
            customer_name=data.customer_name,
            customer_phone=data.customer_phone,
            delivery_address=data.delivery_address,
            neighborhood=data.neighborhood,
            fulfillment_type=data.fulfillment_type,
            payment_method=data.payment_method,
            payment_status=data.payment_status,
            status=OrderStatus.NEW,
            subtotal=money(data.subtotal),
            discount=money(data.discount),
            delivery_fee=money(data.delivery_fee),
            total=money(data.total),
            notes=data.notes,
        )
        db.add(order)
        db.flush()
        order_usage: dict[str, Decimal] = defaultdict(Decimal)
        for item, product, snapshots, usage, unit_cost in lines:
            for ingredient_id, quantity in usage.items():
                order_usage[ingredient_id] += quantity * item.quantity
            db.add(OrderItem(
                order_id=order.id,
                product_id=product.id if product else None,
                product_name=item.name,
                quantity=item.quantity,
                unit_price=money(item.unit_price),
                total=money(item.total_price),
                notes=item.notes,
                selected_options=snapshots,
                unit_cost=unit_cost,
            ))
        stock_service.consume_for_order(db, establishment_id, order.id, dict(order_usage))
        add_event(db, order, "ORDER_CREATED", None, OrderStatus.NEW,
                  {"source": source.value, "integration": integration, "raw_payload": raw_payload or {}})
        try:
            db.commit()
            return get_order_or_404(db, establishment_id, order.id)
        except IntegrityError:
            db.rollback()
            existing = db.scalar(
                select(Order).where(Order.establishment_id == establishment_id, Order.source == source,
                                    Order.external_order_id == data.external_id)
            )
            if existing:
                return get_order_or_404(db, establishment_id, existing.id)
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Nao foi possivel gerar o numero do pedido, tente novamente")


def apply_marketplace_status(db: Session, order: Order, new_status: OrderStatus, payload: dict | None = None) -> bool:
    """Status informado pelo marketplace: so avanca (eventos podem chegar fora de ordem) e cancela de verdade.

    Retorna True se mudou algo. Nao chama o marketplace de volta.
    """
    if order.status in TERMINAL_STATUSES or new_status == order.status:
        return False
    if new_status != OrderStatus.CANCELED and STATUS_RANK.get(new_status, -1) <= STATUS_RANK.get(order.status, -1):
        return False
    previous = order.status
    order.status = new_status
    if new_status == OrderStatus.CANCELED:
        stock_service.return_for_order(db, order.id)
        customer_service.revert_order(db, order)
    elif new_status == OrderStatus.FINISHED:
        customer_service.award_loyalty_point(db, order)
    add_event(db, order, "ORDER_STATUS_CHANGED", previous, new_status, {"by": order.integration or "marketplace", **(payload or {})})
    return True
