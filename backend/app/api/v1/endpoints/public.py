"""Cardapio online publico (sem login): o cliente ve o cardapio, faz o pedido e acompanha pelo codigo."""
from __future__ import annotations

import secrets
from datetime import datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.rate_limit import client_ip, enforce
from app.db import get_db
from app.models.catalog import Category, OptionPricingMode, Product, ProductIngredient, ProductOptionGroup, SalesChannel
from app.models.delivery import DeliveryZone
from app.models.establishment import Establishment
from app.models.order import FulfillmentType, Order, OrderStatus, PaymentMethod, PaymentStatus
from app.schemas.customer import CouponCheck, CouponCheckResult
from app.schemas.order import LocalOrderCreate, OrderItemCreate
from app.services import customer_service
from app.services.availability import option_is_available, product_block_reason
from app.services.order_service import base_price, create_local_order, get_order_or_404

router = APIRouter()

CHANNEL = SalesChannel.LOCAL

# Anti-spam por IP: pedidos e tentativas de cupom (forca bruta de codigos)
ORDERS_PER_IP = 10
ORDERS_WINDOW_SECONDS = 600
COUPON_CHECKS_PER_IP = 30
COUPON_WINDOW_SECONDS = 300


class PublicOption(BaseModel):
    id: str
    name: str
    price_delta: Decimal
    is_available: bool
    sort_order: int = 0
    paused_channels: list[str] = []


class PublicGroup(BaseModel):
    id: str
    name: str
    min_choices: int
    max_choices: int
    sort_order: int = 0
    pricing_mode: OptionPricingMode = OptionPricingMode.SUM
    allow_repeat: bool = False
    depends_on_option_id: str | None = None
    options: list[PublicOption]


class PublicIngredient(BaseModel):
    ingredient_id: str
    name: str
    essential: bool
    paused_channels: list[str] = []


class PublicProduct(BaseModel):
    id: str
    category_id: str
    name: str
    description: str | None = None
    # Preco do cardapio online (canal LOCAL)
    price: Decimal
    image_url: str | None = None
    option_groups: list[PublicGroup]
    ingredients: list[PublicIngredient]


class PublicZone(BaseModel):
    id: str
    name: str
    fee: Decimal
    estimated_minutes: int | None = None


class PublicCategory(BaseModel):
    id: str
    name: str
    sort_order: int


class PublicStore(BaseModel):
    name: str
    slug: str
    phone: str | None = None
    whatsapp: str | None = None
    address: str | None = None
    opening_hours: str | None = None
    logo_url: str | None = None
    preparation_time: int
    # False = loja fechada agora: mostra o cardapio, mas nao aceita pedido
    accepting_orders: bool = True
    loyalty_enabled: bool
    loyalty_goal: int
    loyalty_reward: Decimal
    categories: list[PublicCategory]
    products: list[PublicProduct]
    delivery_zones: list[PublicZone]


class PublicOrderCreate(BaseModel):
    customer_name: str = Field(min_length=2, max_length=140)
    customer_phone: str = Field(max_length=30)
    fulfillment_type: Literal["DELIVERY", "PICKUP"]
    delivery_address: str | None = Field(default=None, max_length=300)
    delivery_zone_id: str | None = None
    payment_method: Literal["PIX", "CARD", "CASH"]
    # Dinheiro: troco para quanto
    change_for: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    notes: str | None = Field(default=None, max_length=300)
    coupon_code: str | None = Field(default=None, max_length=40)
    # A recompensa da fidelidade nao e resgatada aqui: sem login, qualquer um poderia usar o telefone
    # de outra pessoa. O resgate e feito pelo atendente no Pedido local.
    items: list[OrderItemCreate] = Field(min_length=1, max_length=30)


class PublicOrderCreated(BaseModel):
    order_number: str
    public_token: str
    total: Decimal
    status: OrderStatus


class PublicOrderItem(BaseModel):
    quantity: int
    product_name: str
    total: Decimal
    options: list[str] = []


class PublicOrderStatus(BaseModel):
    order_number: str
    status: OrderStatus
    fulfillment_type: FulfillmentType
    payment_method: PaymentMethod
    subtotal: Decimal
    discount: Decimal
    delivery_fee: Decimal
    total: Decimal
    created_at: datetime
    customer_name: str | None = None
    delivery_address: str | None = None
    items: list[PublicOrderItem]
    store_name: str
    store_slug: str | None = None
    store_whatsapp: str | None = None
    store_phone: str | None = None
    preparation_time: int


def _store_or_404(db: Session, slug: str) -> Establishment:
    store = db.scalar(select(Establishment).where(Establishment.slug == slug.lower()))
    if not store or not store.online_menu_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cardapio nao encontrado")
    return store


def _public_product(product: Product) -> PublicProduct:
    return PublicProduct(
        id=product.id,
        category_id=product.category_id,
        name=product.name,
        description=product.description,
        price=base_price(product, CHANNEL),
        image_url=product.image_url,
        option_groups=[
            PublicGroup(
                id=group.id,
                name=group.name,
                min_choices=group.min_choices,
                max_choices=group.max_choices,
                sort_order=group.sort_order,
                pricing_mode=group.pricing_mode,
                allow_repeat=group.allow_repeat,
                depends_on_option_id=group.depends_on_option_id,
                options=[
                    PublicOption(
                        id=option.id,
                        name=option.name,
                        price_delta=option.price_delta,
                        is_available=option_is_available(option, CHANNEL),
                        sort_order=option.sort_order,
                        paused_channels=list(option.paused_channels or []),
                    )
                    for option in group.options
                ],
            )
            for group in product.option_groups
        ],
        ingredients=[
            PublicIngredient(ingredient_id=link.ingredient_id, name=link.ingredient.name, essential=link.essential,
                             paused_channels=list(link.paused_channels or []))
            for link in product.ingredient_links
        ],
    )


@router.get("/stores/{slug}", response_model=PublicStore)
def public_store(slug: str, db: Session = Depends(get_db)) -> PublicStore:
    store = _store_or_404(db, slug)
    products = db.scalars(
        select(Product)
        .where(Product.establishment_id == store.id, Product.is_available.is_(True))
        .options(
            selectinload(Product.option_groups).selectinload(ProductOptionGroup.options),
            selectinload(Product.ingredient_links).selectinload(ProductIngredient.ingredient),
        )
        .order_by(Product.name)
    ).all()
    sellable = [product for product in products if not product_block_reason(product, CHANNEL)]
    used_categories = {product.category_id for product in sellable}
    categories = db.scalars(
        select(Category).where(Category.establishment_id == store.id).order_by(Category.sort_order, Category.name)
    ).all()
    zones = db.scalars(
        select(DeliveryZone).where(DeliveryZone.establishment_id == store.id, DeliveryZone.active.is_(True)).order_by(DeliveryZone.name)
    ).all()
    return PublicStore(
        name=store.name,
        slug=store.slug,
        phone=store.phone,
        whatsapp=store.whatsapp,
        address=store.address,
        opening_hours=store.opening_hours,
        logo_url=store.logo_url,
        preparation_time=store.preparation_time,
        accepting_orders=store.online_orders_open,
        loyalty_enabled=store.loyalty_enabled,
        loyalty_goal=store.loyalty_goal,
        loyalty_reward=store.loyalty_reward,
        categories=[PublicCategory(id=c.id, name=c.name, sort_order=c.sort_order) for c in categories if c.id in used_categories],
        products=[_public_product(product) for product in sellable],
        delivery_zones=[PublicZone(id=z.id, name=z.name, fee=z.fee, estimated_minutes=z.estimated_minutes) for z in zones],
    )


@router.post("/stores/{slug}/orders", response_model=PublicOrderCreated, status_code=201)
def public_order(slug: str, payload: PublicOrderCreate, request: Request, db: Session = Depends(get_db)) -> PublicOrderCreated:
    store = _store_or_404(db, slug)
    if not store.online_orders_open:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A loja nao esta recebendo pedidos agora")
    enforce(f"public-order:{client_ip(request)}", ORDERS_PER_IP, ORDERS_WINDOW_SECONDS,
            "Muitos pedidos seguidos deste aparelho. Aguarde alguns minutos ou fale com a loja.")
    if not customer_service.normalize_phone(payload.customer_phone):
        raise HTTPException(status_code=422, detail="Informe um telefone com DDD")
    delivery = payload.fulfillment_type == "DELIVERY"
    if delivery and not (payload.delivery_address or "").strip():
        raise HTTPException(status_code=422, detail="Informe o endereco de entrega")
    has_zones = db.scalar(select(DeliveryZone.id).where(DeliveryZone.establishment_id == store.id, DeliveryZone.active.is_(True)))
    if delivery and has_zones and not payload.delivery_zone_id:
        raise HTTPException(status_code=422, detail="Escolha o bairro de entrega")
    notes = (payload.notes or "").strip()
    if payload.payment_method == "CASH" and payload.change_for:
        notes = f"{notes} | Troco para R$ {payload.change_for:.2f}".strip(" |")
    local = LocalOrderCreate(
        customer_name=payload.customer_name.strip(),
        customer_phone=payload.customer_phone,
        delivery_address=payload.delivery_address if delivery else None,
        fulfillment_type=FulfillmentType.DELIVERY if delivery else FulfillmentType.PICKUP,
        payment_method=PaymentMethod(payload.payment_method),
        payment_status=PaymentStatus.PENDING,
        notes=notes or None,
        items=payload.items,
        coupon_code=payload.coupon_code,
        delivery_zone_id=payload.delivery_zone_id if delivery else None,
    )
    order = create_local_order(db, store.id, local, raw_payload={"mode": "online_menu"}, trusted_customer_data=False)
    order.public_token = secrets.token_urlsafe(16)
    db.commit()
    return PublicOrderCreated(order_number=order.order_number, public_token=order.public_token, total=order.total, status=order.status)


@router.get("/orders/{token}", response_model=PublicOrderStatus)
def public_order_status(token: str, db: Session = Depends(get_db)) -> PublicOrderStatus:
    order = db.scalar(select(Order).where(Order.public_token == token))
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido nao encontrado")
    order = get_order_or_404(db, order.establishment_id, order.id)
    store = db.get(Establishment, order.establishment_id)
    return PublicOrderStatus(
        order_number=order.order_number,
        status=order.status,
        fulfillment_type=order.fulfillment_type,
        payment_method=order.payment_method,
        subtotal=order.subtotal,
        discount=order.discount,
        delivery_fee=order.delivery_fee,
        total=order.total,
        created_at=order.created_at,
        customer_name=order.customer_name,
        delivery_address=order.delivery_address,
        items=[
            PublicOrderItem(
                quantity=item.quantity,
                product_name=item.product_name,
                total=item.total,
                options=[f"{o.get('quantity', 1)}x {o['name']}" if (o.get("quantity") or 1) > 1 else o["name"] for o in item.selected_options or []],
            )
            for item in order.items
        ],
        store_name=store.name,
        store_slug=store.slug,
        store_whatsapp=store.whatsapp,
        store_phone=store.phone,
        preparation_time=store.preparation_time,
    )


@router.post("/stores/{slug}/coupons/validate", response_model=CouponCheckResult)
def public_coupon(slug: str, payload: CouponCheck, request: Request, db: Session = Depends(get_db)) -> CouponCheckResult:
    store = _store_or_404(db, slug)
    enforce(f"public-coupon:{client_ip(request)}", COUPON_CHECKS_PER_IP, COUPON_WINDOW_SECONDS)
    try:
        _coupon, discount = customer_service.check_coupon(db, store.id, payload.code, payload.subtotal)
    except HTTPException as exc:
        return CouponCheckResult(valid=False, message=str(exc.detail))
    return CouponCheckResult(valid=True, discount=discount, message=f"Desconto de R$ {discount:.2f}")
