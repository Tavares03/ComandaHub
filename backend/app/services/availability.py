"""Disponibilidade por canal: o que pode ser vendido no iFood, no 99 e na loja (LOCAL).

Cada lugar guarda os canais em que esta pausado (paused_channels): o item, cada opcao
dentro de outros itens (ex.: a batata do combo) e cada ingrediente dentro de um item.
Pausar "em todos os lugares" grava a pausa em cada um desses lugares.
"""
from __future__ import annotations

from collections.abc import Iterable

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.catalog import Ingredient, Product, ProductIngredient, ProductOption, ProductOptionGroup, SalesChannel
from app.models.establishment import Establishment
from app.models.order import OrderSource
from app.models.user import EstablishmentMembership, UserRole
from app.schemas.catalog import AvailabilityChange, AvailabilityRequest, AvailabilityResponse, AvailabilityStoreResult

CHANNEL_ORDER = [channel.value for channel in SalesChannel]
EDITOR_ROLES = {UserRole.ADMIN, UserRole.ATTENDANT}


def channel_for_source(source: OrderSource) -> SalesChannel:
    if source == OrderSource.IFOOD:
        return SalesChannel.IFOOD
    if source == OrderSource.NINETY_NINE_FOOD:
        return SalesChannel.NINETY_NINE_FOOD
    return SalesChannel.LOCAL


def _value(channel: SalesChannel | str) -> str:
    return channel.value if isinstance(channel, SalesChannel) else str(channel)


def is_paused(paused: Iterable[str] | None, channel: SalesChannel | str | None) -> bool:
    if channel is None:
        return False
    return _value(channel) in (paused or [])


def product_block_reason(product: Product, channel: SalesChannel | str | None) -> str | None:
    """Por que o item nao pode ser vendido neste canal (None = pode)."""
    if not product.is_available:
        return f"{product.name} esta fora do cardapio"
    if is_paused(product.paused_channels, channel):
        return f"{product.name} esta pausado neste canal"
    for link in product.ingredient_links:
        if link.essential and is_paused(link.paused_channels, channel):
            return f"{product.name} esta indisponivel: acabou {link.ingredient.name}"
    return None


def option_is_available(option: ProductOption, channel: SalesChannel | str | None) -> bool:
    return bool(option.is_available) and not is_paused(option.paused_channels, channel)


def missing_ingredient_names(product: Product, channel: SalesChannel | str | None) -> list[str]:
    """Ingredientes que podem sair do item e estao em falta neste canal (o item vai sem eles)."""
    return [
        link.ingredient.name
        for link in product.ingredient_links
        if not link.essential and is_paused(link.paused_channels, channel)
    ]


def _updated(paused: list[str] | None, channels: list[str], action: str) -> list[str]:
    current = set(paused or [])
    current = current | set(channels) if action == "pause" else current - set(channels)
    return [channel for channel in CHANNEL_ORDER if channel in current]


# ------------------------------------------------------------------ pausar / reativar


def _target_stores(db: Session, establishment: Establishment, membership: EstablishmentMembership, all_establishments: bool) -> list[Establishment]:
    if membership.role not in EDITOR_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissao insuficiente")
    if not all_establishments:
        return [establishment]
    others = db.scalars(
        select(Establishment)
        .join(EstablishmentMembership, EstablishmentMembership.establishment_id == Establishment.id)
        .where(
            EstablishmentMembership.user_id == membership.user_id,
            EstablishmentMembership.role.in_(EDITOR_ROLES),
            Establishment.id != establishment.id,
        )
        .order_by(Establishment.name)
    ).all()
    return [establishment, *others]


def _options_where(db: Session, establishment_id: str, *conditions) -> list[tuple[ProductOption, ProductOptionGroup, Product]]:
    return db.execute(
        select(ProductOption, ProductOptionGroup, Product)
        .join(ProductOptionGroup, ProductOption.group_id == ProductOptionGroup.id)
        .join(Product, ProductOptionGroup.product_id == Product.id)
        .where(Product.establishment_id == establishment_id, *conditions)
        .order_by(Product.name, ProductOptionGroup.sort_order, ProductOption.sort_order)
    ).all()


def _apply_to_product(db: Session, store: Establishment, product: Product, request: AvailabilityRequest, channels: list[str]) -> list[AvailabilityChange]:
    changes = [AvailabilityChange(product_name=product.name, what="Item")]
    if not request.dry_run:
        product.paused_channels = _updated(product.paused_channels, channels, request.action)
    if request.scope == "everywhere":
        for option, group, owner in _options_where(db, store.id, ProductOption.linked_product_id == product.id):
            changes.append(AvailabilityChange(product_name=owner.name, what=f"Opcao {option.name} em {group.name}"))
            if not request.dry_run:
                option.paused_channels = _updated(option.paused_channels, channels, request.action)
    return changes


def set_ingredient_pause(db: Session, establishment_id: str, ingredient: Ingredient, channels: list[str], action: str) -> None:
    """Pausa/reativa o ingrediente em todos os itens da loja (usado pela pausa automatica do estoque)."""
    if not channels:
        return
    request = AvailabilityRequest(target_type="ingredient", target_id=ingredient.id, action=action, channels=channels, scope="everywhere")
    _apply_to_ingredient(db, establishment_id, ingredient, request, _updated([], channels, "pause"), None)


def _apply_to_ingredient(db: Session, store_id: str, ingredient: Ingredient, request: AvailabilityRequest,
                         channels: list[str], selected_names: set[str] | None) -> list[AvailabilityChange]:
    def chosen(product: Product) -> bool:
        return selected_names is None or product.name.strip().lower() in selected_names

    changes: list[AvailabilityChange] = []
    links = db.scalars(
        select(ProductIngredient)
        .join(Product, ProductIngredient.product_id == Product.id)
        .where(ProductIngredient.ingredient_id == ingredient.id)
        .options(selectinload(ProductIngredient.product))
        .order_by(Product.name)
    ).all()
    for link in links:
        if not chosen(link.product):
            continue
        what = "Sai do cardapio (ingrediente principal)" if link.essential else f"Vende sem {ingredient.name}"
        changes.append(AvailabilityChange(product_name=link.product.name, what=what))
        if not request.dry_run:
            link.paused_channels = _updated(link.paused_channels, channels, request.action)
    # Opcoes que usam o ingrediente (Bacon extra) e opcoes que "sao" um item que depende dele
    # como principal (a Batata Frita dentro do combo, quando acaba a batata).
    needs_it = select(ProductIngredient.product_id).where(
        ProductIngredient.ingredient_id == ingredient.id, ProductIngredient.essential.is_(True)
    )
    uses_it = or_(ProductOption.ingredient_id == ingredient.id, ProductOption.linked_product_id.in_(needs_it))
    for option, group, owner in _options_where(db, store_id, uses_it):
        if not chosen(owner):
            continue
        changes.append(AvailabilityChange(product_name=owner.name, what=f"Opcao {option.name} em {group.name}"))
        if not request.dry_run:
            option.paused_channels = _updated(option.paused_channels, channels, request.action)
    return changes


def change_availability(
    db: Session,
    establishment: Establishment,
    membership: EstablishmentMembership,
    request: AvailabilityRequest,
) -> AvailabilityResponse:
    stores = _target_stores(db, establishment, membership, request.all_establishments)
    channels = _updated([], [_value(channel) for channel in request.channels], "pause")
    results: list[AvailabilityStoreResult] = []
    not_found: list[str] = []

    if request.target_type == "product":
        source = db.scalar(select(Product).where(Product.id == request.target_id, Product.establishment_id == establishment.id))
        if not source:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto nao encontrado")
        key = source.name.strip().lower()
        for store in stores:
            product = source if store.id == establishment.id else db.scalar(
                select(Product).where(Product.establishment_id == store.id, func.lower(func.trim(Product.name)) == key)
            )
            if not product:
                not_found.append(store.name)
                continue
            results.append(AvailabilityStoreResult(
                establishment_id=store.id, establishment_name=store.name,
                changes=_apply_to_product(db, store, product, request, channels),
            ))
    else:
        source = db.scalar(select(Ingredient).where(Ingredient.id == request.target_id, Ingredient.establishment_id == establishment.id))
        if not source:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingrediente nao encontrado")
        selected_names: set[str] | None = None
        if request.scope == "selected":
            # Itens escolhidos nesta loja; nas outras lojas vale o item com o mesmo nome.
            names = db.scalars(
                select(Product.name).where(Product.establishment_id == establishment.id, Product.id.in_(request.product_ids))
            ).all()
            selected_names = {name.strip().lower() for name in names}
        key = source.name.strip().lower()
        for store in stores:
            ingredient = source if store.id == establishment.id else db.scalar(
                select(Ingredient).where(Ingredient.establishment_id == store.id, func.lower(func.trim(Ingredient.name)) == key)
            )
            if not ingredient:
                not_found.append(store.name)
                continue
            results.append(AvailabilityStoreResult(
                establishment_id=store.id, establishment_name=store.name,
                changes=_apply_to_ingredient(db, store.id, ingredient, request, channels, selected_names),
            ))

    if request.dry_run:
        db.rollback()
    else:
        db.commit()
    return AvailabilityResponse(results=results, not_found_in=not_found)
