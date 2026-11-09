from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.connectors.simulated import IFoodConnector, LocalOrderConnector, NinetyNineFoodConnector
from app.models.catalog import Product, ProductIngredient, ProductOptionGroup
from app.models.order import Order, OrderSource
from app.services.order_service import create_external_order


CONNECTORS = {
    OrderSource.IFOOD: IFoodConnector,
    OrderSource.NINETY_NINE_FOOD: NinetyNineFoodConnector,
    OrderSource.OWN_DELIVERY: lambda: LocalOrderConnector(OrderSource.OWN_DELIVERY),
    OrderSource.COUNTER: lambda: LocalOrderConnector(OrderSource.COUNTER),
    OrderSource.STORE_PICKUP: lambda: LocalOrderConnector(OrderSource.STORE_PICKUP),
}


def simulate_orders(db: Session, establishment_id: str, source: OrderSource, quantity: int = 1) -> list[Order]:
    if source not in CONNECTORS:
        raise HTTPException(status_code=422, detail="Canal invalido")

    products = db.scalars(
        select(Product)
        .where(Product.establishment_id == establishment_id, Product.is_available.is_(True))
        .options(
            selectinload(Product.option_groups).selectinload(ProductOptionGroup.options),
            selectinload(Product.ingredient_links).selectinload(ProductIngredient.ingredient),
        )
    ).all()
    if not products:
        raise HTTPException(status_code=422, detail="Cadastre produtos antes de simular")

    connector = CONNECTORS[source]()
    created: list[Order] = []
    for _ in range(max(1, min(quantity, 20))):
        try:
            normalized = connector.generate_demo_order(products)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        created.append(create_external_order(db, establishment_id, normalized))
    return created
