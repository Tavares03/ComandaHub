from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.deps import require_establishment_access, require_roles
from app.db import get_db
from app.models.catalog import Ingredient, ProductOption, StockMovement
from app.models.user import UserRole
from app.schemas.catalog import IngredientCreate, IngredientOut, IngredientUpdate, StockEntry, StockMovementOut
from app.services import stock_service

router = APIRouter()

EDITORS = {UserRole.ADMIN, UserRole.ATTENDANT}


def get_ingredient_or_404(db: Session, establishment_id: str, ingredient_id: str) -> Ingredient:
    ingredient = db.scalar(select(Ingredient).where(Ingredient.id == ingredient_id, Ingredient.establishment_id == establishment_id))
    if not ingredient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingrediente nao encontrado")
    return ingredient


@router.get("/{establishment_id}/ingredients", response_model=list[IngredientOut])
def list_ingredients(access=Depends(require_establishment_access), db: Session = Depends(get_db)) -> list[Ingredient]:
    establishment, _membership = access
    return db.scalars(select(Ingredient).where(Ingredient.establishment_id == establishment.id).order_by(Ingredient.name)).all()


@router.post("/{establishment_id}/ingredients", response_model=IngredientOut, status_code=201)
def create_ingredient(payload: IngredientCreate, access=Depends(require_establishment_access), db: Session = Depends(get_db)) -> Ingredient:
    establishment, membership = access
    require_roles(membership, EDITORS)
    ingredient = Ingredient(
        establishment_id=establishment.id,
        name=payload.name.strip(),
        unit=payload.unit,
        min_stock=payload.min_stock,
        cost_per_unit=payload.cost_per_unit,
        auto_paused_channels=[],
    )
    db.add(ingredient)
    db.flush()
    if payload.stock_quantity is not None:
        stock_service.register_entry(db, ingredient, "ADJUST", payload.stock_quantity, note="Estoque inicial")
    db.commit()
    db.refresh(ingredient)
    return ingredient


@router.patch("/{establishment_id}/ingredients/{ingredient_id}", response_model=IngredientOut)
def update_ingredient(
    ingredient_id: str,
    payload: IngredientUpdate,
    access=Depends(require_establishment_access),
    db: Session = Depends(get_db),
) -> Ingredient:
    establishment, membership = access
    require_roles(membership, EDITORS)
    ingredient = get_ingredient_or_404(db, establishment.id, ingredient_id)
    data = payload.model_dump(exclude_unset=True, exclude={"track_stock"})
    if "name" in data and data["name"]:
        data["name"] = data["name"].strip()
    for field, value in data.items():
        if value is not None or field == "min_stock":
            setattr(ingredient, field, value)
    if payload.track_stock is False and ingredient.stock_quantity is not None:
        stock_service.stop_tracking(db, ingredient)
    db.commit()
    db.refresh(ingredient)
    return ingredient


@router.post("/{establishment_id}/ingredients/{ingredient_id}/stock", response_model=IngredientOut)
def stock_entry(
    ingredient_id: str,
    payload: StockEntry,
    access=Depends(require_establishment_access),
    db: Session = Depends(get_db),
) -> Ingredient:
    """Chegou mercadoria (PURCHASE) ou contagem do estoque (ADJUST)."""
    establishment, membership = access
    require_roles(membership, EDITORS | {UserRole.KITCHEN})
    ingredient = get_ingredient_or_404(db, establishment.id, ingredient_id)
    stock_service.register_entry(db, ingredient, payload.kind, payload.quantity, payload.unit_cost, payload.note)
    db.commit()
    db.refresh(ingredient)
    return ingredient


@router.get("/{establishment_id}/ingredients/{ingredient_id}/movements", response_model=list[StockMovementOut])
def stock_movements(
    ingredient_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    access=Depends(require_establishment_access),
    db: Session = Depends(get_db),
) -> list[StockMovement]:
    establishment, _membership = access
    ingredient = get_ingredient_or_404(db, establishment.id, ingredient_id)
    return db.scalars(
        select(StockMovement)
        .where(StockMovement.ingredient_id == ingredient.id)
        .order_by(StockMovement.created_at.desc())
        .limit(limit)
    ).all()


@router.delete("/{establishment_id}/ingredients/{ingredient_id}", status_code=204)
def delete_ingredient(ingredient_id: str, access=Depends(require_establishment_access), db: Session = Depends(get_db)) -> Response:
    """Remove o ingrediente dos itens; as opcoes que apontavam para ele ficam sem vinculo."""
    establishment, membership = access
    require_roles(membership, EDITORS)
    ingredient = get_ingredient_or_404(db, establishment.id, ingredient_id)
    db.execute(update(ProductOption).where(ProductOption.ingredient_id == ingredient.id).values(ingredient_id=None))
    db.delete(ingredient)
    db.commit()
    return Response(status_code=204)
