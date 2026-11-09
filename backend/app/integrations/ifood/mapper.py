"""Converte o pedido do iFood (Order API v1.0) no formato interno, sem acessar o banco.

Os valores sao os que o cliente pagou no iFood: o ComandaHub nao recalcula precos de pedidos do marketplace.
Campos ausentes sao tolerados (o iFood omite blocos que nao se aplicam ao tipo do pedido).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.core.timeutils import to_local
from app.models.order import FulfillmentType, PaymentMethod, PaymentStatus

CENTS = Decimal("0.01")

FULFILLMENT_BY_ORDER_TYPE = {
    "DELIVERY": FulfillmentType.DELIVERY,
    "TAKEOUT": FulfillmentType.PICKUP,
    "INDOOR": FulfillmentType.COUNTER,
    "DINE_IN": FulfillmentType.COUNTER,
}

PAYMENT_LABELS = {
    "CREDIT": "cartao de credito",
    "DEBIT": "cartao de debito",
    "MEAL_VOUCHER": "vale-refeicao",
    "FOOD_VOUCHER": "vale-alimentacao",
    "PIX": "Pix",
    "CASH": "dinheiro",
    "DIGITAL_WALLET": "carteira digital",
    "GIFT_CARD": "vale-presente",
}


@dataclass(frozen=True)
class MarketplaceOption:
    name: str
    quantity: int
    unit_price: Decimal
    external_code: str | None = None
    group_name: str | None = None


@dataclass(frozen=True)
class MarketplaceItem:
    name: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal
    external_code: str | None = None
    notes: str | None = None
    options: list[MarketplaceOption] = field(default_factory=list)


@dataclass(frozen=True)
class MarketplaceOrder:
    external_id: str
    display_id: str | None
    merchant_id: str | None
    fulfillment_type: FulfillmentType
    marketplace_delivery: bool
    customer_name: str | None
    customer_phone: str | None
    delivery_address: str | None
    neighborhood: str | None
    payment_method: PaymentMethod
    payment_status: PaymentStatus
    subtotal: Decimal
    delivery_fee: Decimal
    discount: Decimal
    total: Decimal
    notes: str | None
    items: list[MarketplaceItem]
    is_test: bool = False


def money(value) -> Decimal:
    try:
        return Decimal(str(value if value is not None else 0)).quantize(CENTS)
    except (InvalidOperation, ValueError):
        return Decimal("0.00")


def _quantity(value) -> int:
    try:
        return max(1, int(Decimal(str(value or 1))))
    except (InvalidOperation, ValueError):
        return 1


def _text(value) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _parse_option(raw: dict) -> MarketplaceOption:
    return MarketplaceOption(
        name=_text(raw.get("name")) or "Complemento",
        quantity=_quantity(raw.get("quantity")),
        unit_price=money(raw.get("unitPrice", raw.get("price"))),
        external_code=_text(raw.get("externalCode")),
        group_name=_text(raw.get("groupName")),
    )


def _parse_item(raw: dict) -> MarketplaceItem:
    quantity = _quantity(raw.get("quantity"))
    options = [_parse_option(option) for option in raw.get("options") or []]
    unit_price = money(raw.get("unitPrice", raw.get("price")))
    options_price = money(raw.get("optionsPrice")) if raw.get("optionsPrice") is not None else sum(
        (option.unit_price * option.quantity for option in options), Decimal("0.00")
    )
    total = money(raw.get("totalPrice")) if raw.get("totalPrice") is not None else money((unit_price + options_price) * quantity)
    return MarketplaceItem(
        name=_text(raw.get("name")) or "Item",
        quantity=quantity,
        unit_price=money(total / quantity),
        total_price=total,
        external_code=_text(raw.get("externalCode")),
        notes=_text(raw.get("observations")),
        options=options,
    )


def _address(delivery: dict) -> tuple[str | None, str | None]:
    address = delivery.get("deliveryAddress") or {}
    if not address:
        return None, None
    main = _text(address.get("formattedAddress")) or ", ".join(
        part for part in (_text(address.get("streetName")), _text(address.get("streetNumber"))) if part
    )
    parts = [main, _text(address.get("complement"))]
    reference = _text(address.get("reference"))
    if reference:
        parts.append(f"Ref.: {reference}")
    neighborhood = _text(address.get("neighborhood"))
    if neighborhood and neighborhood.lower() not in (main or "").lower():
        parts.append(neighborhood)
    return " - ".join(part for part in parts if part) or None, neighborhood


def _payment(payments: dict) -> tuple[PaymentMethod, PaymentStatus, list[str]]:
    methods = payments.get("methods") or []
    pending = money(payments.get("pending"))
    notes: list[str] = []
    offline = [method for method in methods if str(method.get("type", "")).upper() == "OFFLINE" or method.get("prepaid") is False]
    if pending <= 0 and not offline:
        return PaymentMethod.ONLINE, PaymentStatus.PAID, notes
    method = offline[0] if offline else (methods[0] if methods else {})
    kind = str(method.get("method", "")).upper()
    label = PAYMENT_LABELS.get(kind, kind.lower() or "na entrega")
    brand = _text((method.get("card") or {}).get("brand"))
    notes.append(f"Cobrar na entrega: {label}{f' {brand}' if brand else ''} - R$ {money(method.get('value') or pending):.2f}")
    change_for = (method.get("cash") or {}).get("changeFor")
    if kind == "CASH" and change_for:
        notes.append(f"Troco para R$ {money(change_for):.2f}")
    if kind == "CASH":
        return PaymentMethod.CASH, PaymentStatus.PENDING, notes
    if kind == "PIX":
        return PaymentMethod.PIX, PaymentStatus.PENDING, notes
    return PaymentMethod.CARD, PaymentStatus.PENDING, notes


def _schedule_note(raw: dict, tz_name: str | None) -> str | None:
    if str(raw.get("orderTiming", "")).upper() != "SCHEDULED":
        return None
    start = (raw.get("schedule") or {}).get("deliveryDateTimeStart") or raw.get("preparationStartDateTime")
    try:
        when = to_local(datetime.fromisoformat(str(start).replace("Z", "+00:00")), tz_name)
        return f"PEDIDO AGENDADO para {when:%d/%m %H:%M}"
    except (TypeError, ValueError):
        return "PEDIDO AGENDADO"


def parse_order(raw: dict, tz_name: str | None = None) -> MarketplaceOrder:
    order_type = str(raw.get("orderType", "DELIVERY")).upper()
    fulfillment = FULFILLMENT_BY_ORDER_TYPE.get(order_type, FulfillmentType.DELIVERY)
    delivery = raw.get("delivery") or {}
    marketplace_delivery = fulfillment == FulfillmentType.DELIVERY and str(delivery.get("deliveredBy", "")).upper() == "IFOOD"
    address, neighborhood = _address(delivery) if fulfillment == FulfillmentType.DELIVERY else (None, None)
    customer = raw.get("customer") or {}
    phone = customer.get("phone") or {}
    payment_method, payment_status, payment_notes = _payment(raw.get("payments") or {})

    total = raw.get("total") or {}
    items = [_parse_item(item) for item in raw.get("items") or []]
    subtotal = money(total.get("subTotal")) if total.get("subTotal") is not None else sum((item.total_price for item in items), Decimal("0.00"))
    # Taxas extras do iFood (ex.: pedido minimo) entram junto da taxa de entrega
    delivery_fee = money(total.get("deliveryFee")) + money(total.get("additionalFees"))
    discount = money(total.get("benefits"))
    order_total = money(total.get("orderAmount")) if total.get("orderAmount") is not None else money(subtotal - discount + delivery_fee)

    notes = [
        "PEDIDO DE TESTE do iFood" if raw.get("isTest") else None,
        _schedule_note(raw, tz_name),
        _text(delivery.get("observations")),
        *payment_notes,
        f"Codigo de coleta: {delivery['pickupCode']}" if delivery.get("pickupCode") else None,
        f"Tel. iFood {phone['number']} (codigo {phone['localizer']})" if phone.get("number") and phone.get("localizer") else None,
        _text(raw.get("extraInfo")),
    ]
    return MarketplaceOrder(
        external_id=str(raw["id"]),
        display_id=_text(raw.get("displayId")),
        merchant_id=_text((raw.get("merchant") or {}).get("id")),
        fulfillment_type=fulfillment,
        marketplace_delivery=marketplace_delivery,
        customer_name=_text(customer.get("name")),
        customer_phone=_text(phone.get("number")),
        delivery_address=address,
        neighborhood=neighborhood,
        payment_method=payment_method,
        payment_status=payment_status,
        subtotal=subtotal,
        delivery_fee=delivery_fee,
        discount=discount,
        total=order_total,
        notes=" | ".join(note for note in notes if note) or None,
        items=items,
        is_test=bool(raw.get("isTest")),
    )
