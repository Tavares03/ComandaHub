"""Estoque por ingrediente.

Cada pedido da baixa na ficha tecnica do item (e das opcoes: combo, adicionais), o cancelamento
devolve, e o historico fica em stock_movements. Quando um ingrediente controlado zera, ele e
pausado sozinho em todos os canais; quando entra mercadoria, volta sozinho (so o que a pausa
automatica fechou: pausa feita a mao continua).
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import Ingredient, Product, ProductOption, SalesChannel, StockMovement
from app.services.availability import CHANNEL_ORDER, is_paused, set_ingredient_pause

ZERO = Decimal("0")


def _is_removal(option: ProductOption) -> bool:
    """"Sem alface" ligado ao ingrediente alface: o cliente tirou, nao gasta."""
    return option.name.strip().lower().startswith("sem ") and not Decimal(option.ingredient_quantity or 0)


def product_recipe(product: Product, skip: set[str] = frozenset()) -> dict[str, Decimal]:
    usage: dict[str, Decimal] = defaultdict(Decimal)
    for link in product.ingredient_links:
        if link.ingredient_id not in skip and link.quantity:
            usage[link.ingredient_id] += Decimal(link.quantity)
    return usage


def line_usage(product: Product, choices: Iterable, channel: SalesChannel | str | None) -> dict[str, Decimal]:
    """Quanto de cada ingrediente uma unidade do item gasta, com as escolhas feitas.

    choices: objetos com .option e .quantity (ResolvedChoice do pedido).
    """
    choices = list(choices)
    removed = {c.option.ingredient_id for c in choices if c.option.ingredient_id and _is_removal(c.option)}
    # Ingrediente em falta no canal: o item sai sem ele, entao nao gasta
    missing = {link.ingredient_id for link in product.ingredient_links if not link.essential and is_paused(link.paused_channels, channel)}
    usage = product_recipe(product, removed | missing)
    for choice in choices:
        option = choice.option
        units = Decimal(choice.quantity)
        if option.linked_product_id and option.linked_product is not None:
            for ingredient_id, quantity in product_recipe(option.linked_product).items():
                usage[ingredient_id] += quantity * units
        if option.ingredient_id and option.ingredient_quantity:
            usage[option.ingredient_id] += Decimal(option.ingredient_quantity) * units
    return dict(usage)


def usage_cost(db: Session, usage: dict[str, Decimal]) -> Decimal:
    if not usage:
        return Decimal("0.00")
    costs = dict(db.execute(select(Ingredient.id, Ingredient.cost_per_unit).where(Ingredient.id.in_(usage))).all())
    total = sum((quantity * Decimal(costs.get(ingredient_id) or 0) for ingredient_id, quantity in usage.items()), ZERO)
    return total.quantize(Decimal("0.01"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fully_paused(ingredient: Ingredient, channel: str) -> bool:
    links = ingredient.product_links
    return bool(links) and all(is_paused(link.paused_channels, channel) for link in links)


def sync_auto_pause(db: Session, ingredient: Ingredient) -> None:
    """Zerou: pausa nos canais que ainda vendiam. Voltou a ter: reativa so esses canais."""
    tracked = ingredient.stock_quantity is not None
    out = tracked and Decimal(ingredient.stock_quantity) <= 0
    if out and not ingredient.auto_paused_channels:
        channels = [channel for channel in CHANNEL_ORDER if not _fully_paused(ingredient, channel)]
        if channels:
            set_ingredient_pause(db, ingredient.establishment_id, ingredient, channels, "pause")
            ingredient.auto_paused_channels = channels
    elif not out and ingredient.auto_paused_channels:
        set_ingredient_pause(db, ingredient.establishment_id, ingredient, list(ingredient.auto_paused_channels), "resume")
        ingredient.auto_paused_channels = []


def _move(db: Session, ingredient: Ingredient, delta: Decimal, reason: str, *, order_id: str | None = None,
          unit_cost: Decimal | None = None, note: str | None = None) -> None:
    ingredient.stock_quantity = Decimal(ingredient.stock_quantity or 0) + delta
    db.add(StockMovement(
        establishment_id=ingredient.establishment_id,
        ingredient_id=ingredient.id,
        reason=reason,
        delta=delta,
        balance=ingredient.stock_quantity,
        order_id=order_id,
        unit_cost=unit_cost,
        note=note,
        created_at=_now(),
    ))
    sync_auto_pause(db, ingredient)


def consume_for_order(db: Session, establishment_id: str, order_id: str, usage: dict[str, Decimal]) -> None:
    """Baixa do pedido. So mexe em ingredientes com estoque controlado."""
    if not usage:
        return
    ingredients = db.scalars(
        select(Ingredient).where(
            Ingredient.establishment_id == establishment_id,
            Ingredient.id.in_(usage),
            Ingredient.stock_quantity.is_not(None),
        )
    ).all()
    for ingredient in ingredients:
        quantity = usage[ingredient.id]
        if quantity:
            _move(db, ingredient, -quantity, "ORDER", order_id=order_id)


def return_for_order(db: Session, order_id: str) -> None:
    """Cancelamento: devolve exatamente o que o pedido baixou."""
    movements = db.scalars(select(StockMovement).where(StockMovement.order_id == order_id)).all()
    if any(movement.reason == "CANCEL" for movement in movements):
        return
    taken: dict[str, Decimal] = defaultdict(Decimal)
    for movement in movements:
        if movement.reason == "ORDER":
            taken[movement.ingredient_id] += -Decimal(movement.delta)
    for ingredient_id, quantity in taken.items():
        ingredient = db.get(Ingredient, ingredient_id)
        if ingredient is not None and ingredient.stock_quantity is not None and quantity:
            _move(db, ingredient, quantity, "CANCEL", order_id=order_id)


def register_entry(db: Session, ingredient: Ingredient, kind: str, quantity: Decimal,
                   unit_cost: Decimal | None = None, note: str | None = None) -> None:
    """PURCHASE soma ao estoque; ADJUST troca pelo valor contado. Comeca a controlar se nao controlava."""
    if kind == "PURCHASE":
        if ingredient.stock_quantity is None:
            ingredient.stock_quantity = ZERO
        if unit_cost is not None:
            ingredient.cost_per_unit = unit_cost
        _move(db, ingredient, quantity, "PURCHASE", unit_cost=unit_cost, note=note)
    else:
        current = Decimal(ingredient.stock_quantity or 0)
        if ingredient.stock_quantity is None:
            ingredient.stock_quantity = ZERO
        _move(db, ingredient, quantity - current, "ADJUST", note=note)


def stop_tracking(db: Session, ingredient: Ingredient) -> None:
    ingredient.stock_quantity = None
    sync_auto_pause(db, ingredient)
