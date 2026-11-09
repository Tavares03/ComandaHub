from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    cash,
    categories,
    customers,
    dashboard,
    delivery,
    establishments,
    ingredients,
    integrations,
    orders,
    products,
    public,
    reports,
    simulator,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(establishments.router, prefix="/establishments", tags=["establishments"])
api_router.include_router(dashboard.router, prefix="/establishments", tags=["dashboard"])
api_router.include_router(orders.router, prefix="/establishments", tags=["orders"])
api_router.include_router(products.router, prefix="/establishments", tags=["products"])
api_router.include_router(categories.router, prefix="/establishments", tags=["categories"])
api_router.include_router(ingredients.router, prefix="/establishments", tags=["ingredients"])
api_router.include_router(customers.router, prefix="/establishments", tags=["customers"])
api_router.include_router(delivery.router, prefix="/establishments", tags=["delivery"])
api_router.include_router(cash.router, prefix="/establishments", tags=["cash"])
api_router.include_router(reports.router, prefix="/establishments", tags=["reports"])
api_router.include_router(integrations.router, prefix="/establishments", tags=["integrations"])
api_router.include_router(public.router, prefix="/public", tags=["public"])
api_router.include_router(simulator.router, prefix="/dev/establishments", tags=["simulator"])
