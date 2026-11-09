from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import require_establishment_access, require_roles
from app.db import get_db
from app.models.catalog import Category, Product
from app.models.user import UserRole
from app.schemas.catalog import CategoryCreate, CategoryOut, CategoryUpdate

router = APIRouter()


def get_category_or_404(db: Session, establishment_id: str, category_id: str) -> Category:
    category = db.scalar(select(Category).where(Category.id == category_id, Category.establishment_id == establishment_id))
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoria nao encontrada")
    return category


@router.get("/{establishment_id}/categories", response_model=list[CategoryOut])
def list_categories(access=Depends(require_establishment_access), db: Session = Depends(get_db)) -> list[Category]:
    establishment, _membership = access
    return db.scalars(select(Category).where(Category.establishment_id == establishment.id).order_by(Category.sort_order, Category.name)).all()


@router.post("/{establishment_id}/categories", response_model=CategoryOut, status_code=201)
def create_category(payload: CategoryCreate, access=Depends(require_establishment_access), db: Session = Depends(get_db)) -> Category:
    establishment, membership = access
    require_roles(membership, {UserRole.ADMIN, UserRole.ATTENDANT})
    category = Category(establishment_id=establishment.id, **payload.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.patch("/{establishment_id}/categories/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: str,
    payload: CategoryUpdate,
    access=Depends(require_establishment_access),
    db: Session = Depends(get_db),
) -> Category:
    establishment, membership = access
    require_roles(membership, {UserRole.ADMIN, UserRole.ATTENDANT})
    category = get_category_or_404(db, establishment.id, category_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    db.commit()
    db.refresh(category)
    return category


@router.delete("/{establishment_id}/categories/{category_id}", status_code=204)
def delete_category(category_id: str, access=Depends(require_establishment_access), db: Session = Depends(get_db)) -> Response:
    establishment, membership = access
    require_roles(membership, {UserRole.ADMIN})
    category = get_category_or_404(db, establishment.id, category_id)
    in_use = db.scalar(select(func.count(Product.id)).where(Product.category_id == category.id)) or 0
    if in_use:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Mova ou exclua os produtos desta categoria antes de remove-la")
    db.delete(category)
    db.commit()
    return Response(status_code=204)
