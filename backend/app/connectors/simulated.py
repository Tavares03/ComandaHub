from __future__ import annotations

import random
from decimal import Decimal
from uuid import uuid4

from app.connectors.base import NormalizedOrder, NormalizedOrderItem
from app.models.catalog import Product
from app.models.order import FulfillmentType, OrderSource, PaymentMethod, PaymentStatus
from app.services.availability import channel_for_source
from app.services.option_picker import can_be_ordered, pick_option_ids

CUSTOMERS = [
    ("Camila Rocha", "1198844-1200", "Rua das Palmeiras, 144"),
    ("Joao Pereira", "1197788-4930", "Av. Brasil, 322"),
    ("Marina Costa", "1195566-3300", "Rua Augusta, 987"),
    ("Rafael Lima", "1196655-8100", "Rua XV de Novembro, 56"),
    ("Pedido sem identificacao", None, None),
]

NOTES = [
    None,
    "Sem cebola",
    "Caprichar no molho",
    "Entregar na portaria",
    "Troco para R$ 100,00",
]


class SimulatedOrderConnector:
    def __init__(self, source: OrderSource) -> None:
        self.source = source

    def receive_orders(self) -> list[NormalizedOrder]:
        return []

    def normalize_order(self, payload: dict) -> NormalizedOrder:
        return payload["normalized"]

    def update_status(self, external_order_id: str, status: str) -> None:
        return None

    def process_cancellation(self, external_order_id: str, reason: str) -> None:
        return None

    def generate_demo_order(self, products: list[Product]) -> NormalizedOrder:
        if not products:
            raise ValueError("Cadastre produtos antes de simular pedidos")

        channel = channel_for_source(self.source)
        orderable = [product for product in products if can_be_ordered(product, channel)]
        if not orderable:
            raise ValueError("Nenhum produto pode ser pedido neste canal: confira pausas e grupos obrigatorios do cardapio")

        customer_name, phone, address = random.choice(CUSTOMERS)
        selected = random.sample(orderable, k=min(random.randint(2, 4), len(orderable)))
        items: list[NormalizedOrderItem] = []
        for product in selected:
            items.append(
                NormalizedOrderItem(
                    product_id=product.id,
                    quantity=random.randint(1, 2),
                    option_ids=pick_option_ids(product, random.Random(), channel=channel),
                    notes=random.choice([None, None, "Caprichar no molho"]),
                )
            )

        fulfillment = FulfillmentType.DELIVERY
        delivery_fee = Decimal("7.90")
        if self.source == OrderSource.STORE_PICKUP:
            fulfillment = FulfillmentType.PICKUP
            delivery_fee = Decimal("0.00")
            address = None
        if self.source == OrderSource.COUNTER:
            fulfillment = FulfillmentType.COUNTER
            delivery_fee = Decimal("0.00")
            address = None
            customer_name = random.choice(["Mesa 04", "Balcao", "Comanda 12"])

        payment_method = PaymentMethod.ONLINE if self.source in {OrderSource.IFOOD, OrderSource.NINETY_NINE_FOOD} else random.choice([PaymentMethod.PIX, PaymentMethod.CARD])
        payment_status = PaymentStatus.PAID if payment_method in {PaymentMethod.ONLINE, PaymentMethod.PIX, PaymentMethod.CARD} else PaymentStatus.PENDING

        return NormalizedOrder(
            external_order_id=f"SIM-{self.source.value}-{uuid4().hex[:12].upper()}",
            source=self.source,
            customer_name=customer_name,
            customer_phone=phone,
            delivery_address=address,
            fulfillment_type=fulfillment,
            payment_method=payment_method,
            payment_status=payment_status,
            delivery_fee=delivery_fee,
            discount=Decimal("0.00"),
            notes=random.choice(NOTES),
            items=items,
            raw_payload={"mode": "simulation", "source": self.source.value},
        )


class IFoodConnector(SimulatedOrderConnector):
    def __init__(self) -> None:
        super().__init__(OrderSource.IFOOD)


class NinetyNineFoodConnector(SimulatedOrderConnector):
    def __init__(self) -> None:
        super().__init__(OrderSource.NINETY_NINE_FOOD)


class LocalOrderConnector(SimulatedOrderConnector):
    def __init__(self, source: OrderSource = OrderSource.OWN_DELIVERY) -> None:
        super().__init__(source)
