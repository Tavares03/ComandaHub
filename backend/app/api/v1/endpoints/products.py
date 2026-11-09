from __future__ import annotations

from decimal import ROUND_FLOOR, Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import require_establishment_access, require_roles
from app.db import get_db
from app.models.catalog import Category, Ingredient, Product, ProductIngredient, ProductOption, ProductOptionGroup
from app.models.user import UserRole
from app.schemas.catalog import (
    AvailabilityRequest,
    AvailabilityResponse,
    ChannelPriceBulk,
    ProductCreate,
    ProductIngredientIn,
    ProductOptionGroupCreate,
    ProductOut,
    ProductUpdate,
)
from app.services.availability import change_availability

router = APIRouter()


def product_query():
    return select(Product).options(
        selectinload(Product.category),
        selectinload(Product.option_groups).selectinload(ProductOptionGroup.options),
        selectinload(Product.ingredient_links).selectinload(ProductIngredient.ingredient),
    )


def assert_category(db: Session, establishment_id: str, category_id: str) -> None:
    exists = db.scalar(select(Category.id).where(Category.id == category_id, Category.establishment_id == establishment_id))
    if not exists:
        raise HTTPException(status_code=422, detail="Categoria invalida")


def _assert_belongs(db: Session, model, ids: set[str], establishment_id: str, message: str) -> None:
    if not ids:
        return
    found = set(db.scalars(select(model.id).where(model.id.in_(ids), model.establishment_id == establishment_id)).all())
    if ids - found:
        raise HTTPException(status_code=422, detail=message)


def apply_option_groups(db: Session, product: Product, payload_groups: list[ProductOptionGroupCreate], establishment_id: str) -> None:
    """Salva os grupos na ordem enviada.

    Grupos e opcoes enviados com id sao atualizados no lugar: mantem o id (carrinhos abertos
    continuam validos) e as pausas por canal. O que nao veio no envio e removido.
    """
    linked = {option.linked_product_id for group in payload_groups for option in group.options if option.linked_product_id}
    _assert_belongs(db, Product, linked, establishment_id, "Opcao ligada a um produto que nao existe nesta loja")
    if product.id and product.id in linked:
        raise HTTPException(status_code=422, detail="Uma opcao nao pode ser ligada ao proprio produto")
    ingredients = {option.ingredient_id for group in payload_groups for option in group.options if option.ingredient_id}
    _assert_belongs(db, Ingredient, ingredients, establishment_id, "Opcao ligada a um ingrediente que nao existe nesta loja")

    existing_groups = {group.id: group for group in product.option_groups}
    saved_groups: list[ProductOptionGroup] = []
    for group_index, group_payload in enumerate(payload_groups):
        group = existing_groups.pop(group_payload.id, None) if group_payload.id else None
        if group is None:
            group = ProductOptionGroup()
        group.name = group_payload.name
        group.min_choices = group_payload.min_choices
        group.max_choices = group_payload.max_choices
        group.pricing_mode = group_payload.pricing_mode
        group.allow_repeat = group_payload.allow_repeat
        group.sort_order = group_index

        existing_options = {option.id: option for option in group.options}
        saved_options: list[ProductOption] = []
        for option_index, option_payload in enumerate(group_payload.options):
            option = existing_options.pop(option_payload.id, None) if option_payload.id else None
            if option is None:
                option = ProductOption(paused_channels=[])
            option.name = option_payload.name
            option.price_delta = option_payload.price_delta
            option.is_available = option_payload.is_available
            option.linked_product_id = option_payload.linked_product_id
            option.ingredient_id = option_payload.ingredient_id
            option.ingredient_quantity = option_payload.ingredient_quantity
            option.sort_order = option_index
            saved_options.append(option)
        group.options = saved_options
        saved_groups.append(group)
    product.option_groups = saved_groups

    # Os ids das opcoes novas so existem depois do flush; entao ligamos os grupos condicionais.
    db.flush()
    for group, group_payload in zip(saved_groups, payload_groups):
        ref = group_payload.depends_on
        group.depends_on_option_id = saved_groups[ref.group].options[ref.option].id if ref else None


def apply_ingredients(db: Session, product: Product, items: list[ProductIngredientIn], establishment_id: str) -> None:
    """Salva os ingredientes do item mantendo as pausas dos que ja existiam."""
    _assert_belongs(db, Ingredient, {item.ingredient_id for item in items}, establishment_id, "Ingrediente invalido")
    existing = {link.ingredient_id: link for link in product.ingredient_links}
    links: list[ProductIngredient] = []
    seen: set[str] = set()
    for item in items:
        if item.ingredient_id in seen:
            continue
        seen.add(item.ingredient_id)
        link = existing.pop(item.ingredient_id, None) or ProductIngredient(ingredient_id=item.ingredient_id, paused_channels=[])
        link.essential = item.essential
        link.quantity = item.quantity
        link.sort_order = len(links)
        links.append(link)
    product.ingredient_links = links


def channel_prices_json(prices) -> dict[str, str]:
    return {channel.value if hasattr(channel, "value") else str(channel): str(Decimal(value).quantize(Decimal("0.01")))
            for channel, value in prices.items()}


def round_up_to_90(value: Decimal) -> Decimal:
    """36,00 -> 36,90 | 35,95 -> 36,90 | 35,40 -> 35,90 (nunca arredonda para baixo)."""
    whole = value.to_integral_value(rounding=ROUND_FLOOR)
    candidate = whole + Decimal("0.90")
    return candidate if candidate >= value else candidate + 1


def load_product(db: Session, establishment_id: str, product_id: str) -> Product:
    product = db.scalar(
        product_query()
        .where(Product.id == product_id, Product.establishment_id == establishment_id)
        .execution_options(populate_existing=True)
    )
    if not product:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")
    return product


@router.get("/{establishment_id}/products", response_model=list[ProductOut])
def list_products(access=Depends(require_establishment_access), db: Session = Depends(get_db)) -> list[Product]:
    establishment, _membership = access
    return db.scalars(product_query().where(Product.establishment_id == establishment.id).order_by(Product.name)).all()


@router.post("/{establishment_id}/products", response_model=ProductOut, status_code=201)
def create_product(payload: ProductCreate, access=Depends(require_establishment_access), db: Session = Depends(get_db)) -> Product:
    establishment, membership = access
    require_roles(membership, {UserRole.ADMIN, UserRole.ATTENDANT})
    assert_category(db, establishment.id, payload.category_id)
    data = payload.model_dump(exclude={"option_groups", "ingredients", "channel_prices"})
    product = Product(establishment_id=establishment.id, paused_channels=[], channel_prices=channel_prices_json(payload.channel_prices), **data)
    db.add(product)
    apply_ingredients(db, product, payload.ingredients, establishment.id)
    apply_option_groups(db, product, payload.option_groups, establishment.id)
    db.commit()
    return load_product(db, establishment.id, product.id)


@router.patch("/{establishment_id}/products/{product_id}", response_model=ProductOut)
def update_product(
    product_id: str,
    payload: ProductUpdate,
    access=Depends(require_establishment_access),
    db: Session = Depends(get_db),
) -> Product:
    establishment, membership = access
    require_roles(membership, {UserRole.ADMIN, UserRole.ATTENDANT})
    product = load_product(db, establishment.id, product_id)
    if payload.category_id:
        assert_category(db, establishment.id, payload.category_id)
    data = payload.model_dump(exclude_unset=True, exclude={"option_groups", "ingredients", "channel_prices"})
    for field, value in data.items():
        setattr(product, field, value)
    if payload.channel_prices is not None:
        product.channel_prices = channel_prices_json(payload.channel_prices)
    if payload.ingredients is not None:
        apply_ingredients(db, product, payload.ingredients, establishment.id)
    if payload.option_groups is not None:
        apply_option_groups(db, product, payload.option_groups, establishment.id)
    db.commit()
    return load_product(db, establishment.id, product.id)


@router.delete("/{establishment_id}/products/{product_id}", response_model=ProductOut)
def deactivate_product(product_id: str, access=Depends(require_establishment_access), db: Session = Depends(get_db)) -> Product:
    establishment, membership = access
    require_roles(membership, {UserRole.ADMIN, UserRole.ATTENDANT})
    product = load_product(db, establishment.id, product_id)
    product.is_available = False
    db.commit()
    return load_product(db, establishment.id, product.id)


@router.post("/{establishment_id}/availability", response_model=AvailabilityResponse)
def update_availability(
    payload: AvailabilityRequest,
    access=Depends(require_establishment_access),
    db: Session = Depends(get_db),
) -> AvailabilityResponse:
    """Pausa ou reativa um item/ingrediente por canal, so nele ou em todo lugar que o usa, em uma ou todas as lojas."""
    establishment, membership = access
    return change_availability(db, establishment, membership, payload)


@router.post("/{establishment_id}/channel-prices", response_model=list[ProductOut])
def bulk_channel_prices(
    payload: ChannelPriceBulk,
    access=Depends(require_establishment_access),
    db: Session = Depends(get_db),
) -> list[Product]:
    """Preco do canal = preco normal + percentual (ex.: iFood +20%), opcionalmente arredondado para ,90."""
    establishment, membership = access
    require_roles(membership, {UserRole.ADMIN, UserRole.ATTENDANT})
    query = product_query().where(Product.establishment_id == establishment.id)
    if payload.product_ids:
        query = query.where(Product.id.in_(payload.product_ids))
    products = db.scalars(query).all()
    channel = payload.channel.value
    for product in products:
        prices = dict(product.channel_prices or {})
        if payload.percent is None:
            prices.pop(channel, None)
        else:
            value = (Decimal(product.price) * (1 + payload.percent / 100)).quantize(Decimal("0.01"))
            if payload.round_to_90:
                value = round_up_to_90(value)
            prices[channel] = str(max(value, Decimal("0.01")))
        product.channel_prices = prices
    db.commit()
    return db.scalars(query.order_by(Product.name).execution_options(populate_existing=True)).all()
