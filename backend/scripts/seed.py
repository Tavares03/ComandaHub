from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
import app.db as db_module
from app.models.customer import Coupon
from app.models.delivery import Courier, DeliveryZone
from app.models.catalog import Category, Ingredient, OptionPricingMode, Product, ProductIngredient, ProductOption, ProductOptionGroup
from app.models.establishment import Establishment
from app.models.order import FulfillmentType, Order, OrderSource, OrderStatus, PaymentMethod, PaymentStatus
from app.models.user import EstablishmentMembership, User, UserRole
from app.schemas.order import OrderItemCreate
from app.services.option_picker import can_be_ordered, pick_option_ids
from app.services.order_service import add_event, create_order

BURGER_IMAGE = "https://images.unsplash.com/photo-1550547660-d9450f859349?auto=format&fit=crop&w=900&q=80"
PIZZA_IMAGE = "https://images.unsplash.com/photo-1513104890138-7c749659a591?auto=format&fit=crop&w=900&q=80"


@dataclass(frozen=True)
class GroupSpec:
    name: str
    min_choices: int
    max_choices: int  # 0 = sem limite
    options: list[tuple[str, str]]
    pricing_mode: OptionPricingMode = OptionPricingMode.SUM
    allow_repeat: bool = False
    # Opcao -> produto do cardapio que ela representa (batata do combo = produto Batata Frita)
    products: dict[str, str] = field(default_factory=dict)
    # Opcao -> ingrediente que ela usa (Sem alface / Bacon extra)
    ingredients: dict[str, str] = field(default_factory=dict)
    # Grupo condicional: (grupo, opcao) que libera este grupo
    depends_on: tuple[str, str] | None = None


@dataclass(frozen=True)
class ProductSpec:
    category: str
    name: str
    description: str
    price: str
    image_url: str | None = None
    groups: list[GroupSpec] = field(default_factory=list)
    # (ingrediente, principal). Principal: sem ele o item sai do cardapio.
    ingredients: list[tuple[str, bool]] = field(default_factory=list)


@dataclass(frozen=True)
class CatalogSpec:
    categories: list[str]
    products: list[ProductSpec]


# ---------------------------------------------------------------- hamburguerias

PONTO_DA_CARNE = GroupSpec("Ponto da carne", 1, 1, [("Mal passado", "0"), ("Ao ponto", "0"), ("Bem passado", "0")])
ADICIONAIS = GroupSpec(
    "Adicionais",
    0,
    5,
    [("Hamburguer extra", "9.00"), ("Bacon extra", "5.00"), ("Cheddar extra", "4.00"), ("Ovo", "3.00"), ("Cebola caramelizada", "3.00")],
    allow_repeat=True,
    ingredients={"Hamburguer extra": "Carne bovina", "Bacon extra": "Bacon", "Cheddar extra": "Cheddar", "Ovo": "Ovo",
                 "Cebola caramelizada": "Cebola"},
)
RETIRAR = GroupSpec(
    "Retirar ingredientes",
    0,
    0,
    [("Sem alface", "0"), ("Sem tomate", "0"), ("Sem cebola", "0"), ("Sem picles", "0"), ("Sem molho", "0")],
    ingredients={"Sem alface": "Alface", "Sem tomate": "Tomate", "Sem cebola": "Cebola", "Sem picles": "Picles",
                 "Sem molho": "Molho da casa"},
)
COMBO_TRIGGER = ("Combo", "Fazer combo (acompanhamento + bebida)")


def combo_groups(combo_price: str) -> list[GroupSpec]:
    """Combo dentro do hamburguer: "Fazer combo" libera a escolha do acompanhamento e da bebida."""
    return [
        GroupSpec(COMBO_TRIGGER[0], 0, 1, [(COMBO_TRIGGER[1], combo_price)]),
        GroupSpec(
            "Acompanhamento do combo",
            1,
            1,
            [("Batata Frita", "0"), ("Onion Rings", "4.00"), ("Batata com Cheddar", "8.00")],
            products={"Batata Frita": "Batata Frita", "Onion Rings": "Onion Rings", "Batata com Cheddar": "Batata com Cheddar"},
            depends_on=COMBO_TRIGGER,
        ),
        GroupSpec(
            "Bebida do combo",
            1,
            1,
            [("Coca-Cola", "0"), ("Guarana", "0"), ("Agua", "0")],
            products={"Coca-Cola": "Coca-Cola", "Guarana": "Guarana", "Agua": "Agua"},
            depends_on=COMBO_TRIGGER,
        ),
    ]


def burger_groups(combo_price: str = "18.00", with_point: bool = True) -> list[GroupSpec]:
    return [*([PONTO_DA_CARNE] if with_point else []), *combo_groups(combo_price), ADICIONAIS, RETIRAR]


BEBIDA_KIDS = GroupSpec("Bebida", 1, 1, [("Suco de uva", "0"), ("Suco de laranja", "0"), ("Agua sem gas", "0")])
MOLHOS = GroupSpec("Molhos", 0, 3, [("Maionese verde", "2.50"), ("Barbecue", "2.50"), ("Cheddar cremoso", "3.50")],
                   ingredients={"Cheddar cremoso": "Cheddar"})

# Unidade e custo de demonstracao (R$ por unidade) e quanto vai em cada item por padrao.
INGREDIENT_INFO: dict[str, tuple[str, str, str]] = {
    # nome: (unidade, custo por unidade, quantidade padrao na ficha tecnica)
    "Pao brioche": ("un", "1.20", "1"),
    "Carne bovina": ("kg", "45.00", "0.09"),
    "Queijo": ("kg", "40.00", "0.02"),
    "Cheddar": ("kg", "45.00", "0.03"),
    "Alface": ("kg", "12.00", "0.01"),
    "Tomate": ("kg", "8.00", "0.02"),
    "Cebola": ("kg", "6.00", "0.015"),
    "Picles": ("kg", "20.00", "0.01"),
    "Molho da casa": ("L", "15.00", "0.02"),
    "Bacon": ("kg", "50.00", "0.03"),
    "Frango empanado": ("kg", "32.00", "0.12"),
    "Batata": ("kg", "9.00", "0.25"),
    "Ovo": ("un", "0.80", "1"),
}
# Excecoes da quantidade padrao: (item, ingrediente) -> quantidade
RECIPE_OVERRIDES: dict[tuple[str, str], str] = {
    ("Double Smash", "Carne bovina"): "0.18",
    ("Double Smash", "Cheddar"): "0.04",
    ("Combo Kids", "Batata"): "0.10",
    ("Combo Kids", "Carne bovina"): "0.06",
    ("Onion Rings", "Cebola"): "0.12",
}
# Quanto cada adicional gasta do ingrediente
OPTION_QUANTITIES: dict[str, str] = {
    "Hamburguer extra": "0.09",
    "Bacon extra": "0.03",
    "Cheddar extra": "0.03",
    "Ovo": "1",
    "Cebola caramelizada": "0.03",
    "Cheddar cremoso": "0.03",
}

SALADA = [("Alface", False), ("Tomate", False), ("Cebola", False), ("Picles", False), ("Molho da casa", False)]
BEEF_BURGER = [("Pao brioche", True), ("Carne bovina", True), ("Queijo", False), *SALADA]

BURGER_CATALOG = CatalogSpec(
    categories=["Hamburgueres", "Combos", "Acompanhamentos", "Bebidas", "Sobremesas"],
    products=[
        # Combo agora e uma escolha dentro do hamburguer (grupo "Combo"), e nao um produto separado.
        ProductSpec("Hamburgueres", "Smash Burger", "Pao brioche, blend 90g, queijo e molho da casa", "24.90", BURGER_IMAGE,
                    burger_groups("18.00"), BEEF_BURGER),
        ProductSpec("Hamburgueres", "Double Smash", "Dois blends 90g, cheddar duplo e picles", "34.90", BURGER_IMAGE,
                    burger_groups("22.00"), [("Pao brioche", True), ("Carne bovina", True), ("Cheddar", False), *SALADA]),
        ProductSpec("Hamburgueres", "Bacon Burger", "Blend bovino, cheddar, bacon crocante e cebola caramelizada", "32.90", BURGER_IMAGE,
                    burger_groups("18.00"), [("Pao brioche", True), ("Carne bovina", True), ("Cheddar", False), ("Bacon", False), *SALADA]),
        ProductSpec("Hamburgueres", "Cheese Burger", "Classico com queijo prato e maionese verde", "26.90", BURGER_IMAGE,
                    burger_groups("18.00"), BEEF_BURGER),
        ProductSpec("Hamburgueres", "Chicken Burger", "Frango empanado, coleslaw e molho levemente picante", "28.90", BURGER_IMAGE,
                    burger_groups("18.00", with_point=False), [("Pao brioche", True), ("Frango empanado", True), *SALADA]),
        ProductSpec("Combos", "Combo Kids", "Mini burger, batata pequena e suco", "31.90", BURGER_IMAGE, [BEBIDA_KIDS, RETIRAR],
                    [("Pao brioche", True), ("Carne bovina", True), ("Batata", True), ("Alface", False), ("Tomate", False)]),
        ProductSpec("Acompanhamentos", "Batata Frita", "Batata sequinha com sal da casa", "16.90", BURGER_IMAGE, [MOLHOS],
                    [("Batata", True)]),
        ProductSpec("Acompanhamentos", "Batata com Cheddar", "Batata, cheddar cremoso e bacon", "24.90", BURGER_IMAGE, [],
                    [("Batata", True), ("Cheddar", False), ("Bacon", False)]),
        ProductSpec("Acompanhamentos", "Onion Rings", "Aneis de cebola empanados", "21.90", BURGER_IMAGE, [MOLHOS],
                    [("Cebola", True)]),
        ProductSpec("Bebidas", "Coca-Cola", "Lata 350ml", "7.90", BURGER_IMAGE),
        ProductSpec("Bebidas", "Guarana", "Lata 350ml", "7.50", BURGER_IMAGE),
        ProductSpec("Bebidas", "Agua", "Garrafa 500ml", "5.00", BURGER_IMAGE),
        ProductSpec("Sobremesas", "Milkshake Chocolate", "Chocolate, chantilly e calda", "22.90", BURGER_IMAGE),
        ProductSpec("Sobremesas", "Brownie", "Brownie de chocolate com calda", "18.90", BURGER_IMAGE),
    ],
)

# ---------------------------------------------------------------- pizzaria

# (sabor, acrescimo na pizza grande). Nos outros tamanhos o acrescimo e proporcional.
SALTY_FLAVORS = [
    ("Mussarela", "0"),
    ("Calabresa", "0"),
    ("Margherita", "0"),
    ("Portuguesa", "6.00"),
    ("Frango com catupiry", "6.00"),
    ("Quatro queijos", "8.00"),
    ("Pepperoni", "8.00"),
    ("Camarao", "20.00"),
]
SWEET_FLAVORS = [("Chocolate", "0"), ("Banana com canela", "0"), ("Prestigio", "4.00"), ("Romeu e Julieta", "4.00")]
# Evite nomes comecando com "Sem": a cozinha destaca esses como retirada de ingrediente.
CRUSTS = [("Borda tradicional", "0"), ("Catupiry", "10.00"), ("Cheddar", "10.00"), ("Chocolate", "12.00")]


def scaled(options: list[tuple[str, str]], factor: str) -> list[tuple[str, str]]:
    return [(name, str((Decimal(price) * Decimal(factor)).quantize(Decimal("0.01")))) for name, price in options]


def pizza_groups(max_flavors: int, factor: str, flavors: list[tuple[str, str]] = SALTY_FLAVORS, with_crust: bool = True) -> list[GroupSpec]:
    groups = [GroupSpec("Sabores", 1, max_flavors, scaled(flavors, factor), pricing_mode=OptionPricingMode.MAX)]
    if with_crust:
        groups.append(GroupSpec("Borda", 1, 1, scaled(CRUSTS, factor)))
    return groups


PIZZA_CATALOG = CatalogSpec(
    categories=["Pizzas salgadas", "Pizzas doces", "Bebidas"],
    products=[
        ProductSpec("Pizzas salgadas", "Pizza Broto", "4 fatias, 1 sabor", "34.90", PIZZA_IMAGE, pizza_groups(1, "0.6")),
        ProductSpec("Pizzas salgadas", "Pizza Grande", "8 fatias, ate 2 sabores (meio a meio)", "59.90", PIZZA_IMAGE, pizza_groups(2, "1")),
        ProductSpec("Pizzas salgadas", "Pizza Familia", "12 fatias, ate 3 sabores", "79.90", PIZZA_IMAGE, pizza_groups(3, "1.4")),
        ProductSpec("Pizzas doces", "Pizza Doce Grande", "8 fatias, ate 2 sabores", "54.90", PIZZA_IMAGE,
                    pizza_groups(2, "1", SWEET_FLAVORS, with_crust=False)),
        ProductSpec("Bebidas", "Coca-Cola 2L", "Garrafa 2 litros", "14.90"),
        ProductSpec("Bebidas", "Guarana 2L", "Garrafa 2 litros", "12.90"),
        ProductSpec("Bebidas", "Coca-Cola lata", "Lata 350ml", "6.90"),
        ProductSpec("Bebidas", "Agua", "Garrafa 500ml", "4.00"),
    ],
)

# Pedidos de hoje: (status, minutos atras). Os indices batem com a ordem dos canais em seed_orders,
# entao "saiu para entrega" sempre cai num pedido de delivery.
TODAY_ORDERS = [
    (OrderStatus.NEW, 3),
    (OrderStatus.NEW, 6),
    (OrderStatus.ACCEPTED, 10),
    (OrderStatus.PREPARING, 16),
    (OrderStatus.PREPARING, 21),
    (OrderStatus.READY, 27),
    (OrderStatus.OUT_FOR_DELIVERY, 34),
    (OrderStatus.FINISHED, 70),
    (OrderStatus.FINISHED, 110),
    (OrderStatus.CANCELED, 140),
]
SEED_ORDER_COUNT = 34


def seed_timeline(index: int, now: datetime) -> tuple[OrderStatus, datetime]:
    """Hoje: pedidos recentes em todas as etapas. Dias anteriores: finalizados (alguns cancelados)."""
    if index < len(TODAY_ORDERS):
        status, minutes_ago = TODAY_ORDERS[index]
        return status, now - timedelta(minutes=minutes_ago)
    days_ago = 1 + index % 6
    status = OrderStatus.CANCELED if index % 8 == 0 else OrderStatus.FINISHED
    return status, now - timedelta(days=days_ago, hours=index % 9, minutes=7 * index)


def get_or_create_establishment(db: Session, name: str, **data) -> Establishment:
    establishment = db.scalar(select(Establishment).where(Establishment.name == name))
    if establishment:
        return establishment
    establishment = Establishment(name=name, **data)
    db.add(establishment)
    db.flush()
    return establishment


def get_or_create_user(db: Session, name: str, email: str, password: str = "demo123") -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user:
        return user
    user = User(name=name, email=email, password_hash=hash_password(password), is_active=True)
    db.add(user)
    db.flush()
    return user


def ensure_membership(db: Session, user: User, establishment: Establishment, role: UserRole) -> None:
    membership = db.scalar(
        select(EstablishmentMembership).where(
            EstablishmentMembership.user_id == user.id,
            EstablishmentMembership.establishment_id == establishment.id,
        )
    )
    if membership:
        membership.role = role
        return
    db.add(EstablishmentMembership(user_id=user.id, establishment_id=establishment.id, role=role))


def ensure_option_groups(
    db: Session,
    product: Product,
    specs: list[GroupSpec],
    products_by_name: dict[str, Product],
    ingredients_by_name: dict[str, Ingredient],
) -> None:
    """Cria grupos e opcoes que faltam. Nunca altera o que a loja ja configurou.

    O seed roda a cada subida do container: sobrescrever desfaria o que a loja
    configurou pelo Cardapio. Grupos novos entram logo depois do grupo que os
    precede no modelo (ex.: o combo entra depois do ponto da carne). So preenche
    vinculos de opcoes (produto/ingrediente) que ainda estao vazios.
    """
    existing = {group.name: group for group in product.option_groups}
    ordered = sorted(product.option_groups, key=lambda group: (group.sort_order, group.name))
    created: list[tuple[ProductOptionGroup, GroupSpec]] = []
    previous: ProductOptionGroup | None = None
    for spec in specs:
        group = existing.get(spec.name)
        if not group:
            group = ProductOptionGroup(
                name=spec.name,
                min_choices=spec.min_choices,
                max_choices=spec.max_choices,
                pricing_mode=spec.pricing_mode,
                allow_repeat=spec.allow_repeat,
            )
            product.option_groups.append(group)
            ordered.insert(ordered.index(previous) + 1 if previous is not None else 0, group)
            created.append((group, spec))
        options = {option.name: option for option in group.options}
        next_option_sort = max((option.sort_order for option in group.options), default=-1) + 1
        for option_name, price in spec.options:
            option = options.get(option_name)
            if not option:
                option = ProductOption(name=option_name, price_delta=Decimal(price), sort_order=next_option_sort, paused_channels=[])
                group.options.append(option)
                next_option_sort += 1
            linked = products_by_name.get(spec.products.get(option_name, ""))
            if linked and not option.linked_product_id:
                option.linked_product_id = linked.id
            ingredient = ingredients_by_name.get(spec.ingredients.get(option_name, ""))
            if ingredient and not option.ingredient_id:
                option.ingredient_id = ingredient.id
            if ingredient and not option.ingredient_quantity and option_name in OPTION_QUANTITIES:
                option.ingredient_quantity = Decimal(OPTION_QUANTITIES[option_name])
        previous = group
    if not created:
        return
    for index, group in enumerate(ordered):
        group.sort_order = index
    db.flush()
    by_name = {group.name: group for group in product.option_groups}
    for group, spec in created:
        if not spec.depends_on:
            continue
        trigger_group = by_name.get(spec.depends_on[0])
        trigger = next((option for option in trigger_group.options if option.name == spec.depends_on[1]), None) if trigger_group else None
        group.depends_on_option_id = trigger.id if trigger else None


def ensure_ingredient_links(product: Product, specs: list[tuple[str, bool]], ingredients_by_name: dict[str, Ingredient]) -> None:
    """Liga os ingredientes que faltam no item, sem mexer nos que a loja ja configurou."""
    links = {link.ingredient_id: link for link in product.ingredient_links}
    next_sort = max((link.sort_order for link in product.ingredient_links), default=-1) + 1
    for name, essential in specs:
        ingredient = ingredients_by_name[name]
        quantity = Decimal(RECIPE_OVERRIDES.get((product.name, name), INGREDIENT_INFO.get(name, ("un", "0", "0"))[2]))
        link = links.get(ingredient.id)
        if link:
            # So preenche a ficha tecnica que ainda esta vazia
            if not link.quantity:
                link.quantity = quantity
            continue
        link = ProductIngredient(ingredient_id=ingredient.id, essential=essential, sort_order=next_sort, quantity=quantity, paused_channels=[])
        product.ingredient_links.append(link)
        links[ingredient.id] = link
        next_sort += 1


def seed_catalog(db: Session, establishment: Establishment, catalog: CatalogSpec) -> None:
    categories: dict[str, Category] = {}
    for index, name in enumerate(catalog.categories):
        category = db.scalar(select(Category).where(Category.establishment_id == establishment.id, Category.name == name))
        if not category:
            category = Category(establishment_id=establishment.id, name=name, sort_order=index)
            db.add(category)
            db.flush()
        categories[name] = category

    ingredient_names = {name for spec in catalog.products for name, _essential in spec.ingredients}
    ingredient_names |= {name for spec in catalog.products for group in spec.groups for name in group.ingredients.values()}
    ingredients_by_name: dict[str, Ingredient] = {}
    for name in sorted(ingredient_names):
        ingredient = db.scalar(select(Ingredient).where(Ingredient.establishment_id == establishment.id, Ingredient.name == name))
        unit, cost, _quantity = INGREDIENT_INFO.get(name, ("un", "0", "0"))
        if not ingredient:
            ingredient = Ingredient(establishment_id=establishment.id, name=name, unit=unit, cost_per_unit=Decimal(cost),
                                    auto_paused_channels=[])
            db.add(ingredient)
            db.flush()
        elif not ingredient.cost_per_unit and ingredient.unit == "un":
            # Ingrediente criado antes de existir unidade/custo: preenche os dados de demonstracao
            ingredient.unit = unit
            ingredient.cost_per_unit = Decimal(cost)
        ingredients_by_name[name] = ingredient

    # Primeiro todos os produtos existem; depois os grupos, que podem apontar para eles (combo).
    products_by_name: dict[str, Product] = {}
    for spec in catalog.products:
        product = db.scalar(select(Product).where(Product.establishment_id == establishment.id, Product.name == spec.name))
        if not product:
            product = Product(
                establishment_id=establishment.id,
                category_id=categories[spec.category].id,
                name=spec.name,
                description=spec.description,
                price=Decimal(spec.price),
                image_url=spec.image_url,
                is_available=True,
                paused_channels=[],
            )
            db.add(product)
            db.flush()
        products_by_name[spec.name] = product

    for spec in catalog.products:
        product = products_by_name[spec.name]
        ensure_ingredient_links(product, spec.ingredients, ingredients_by_name)
        ensure_option_groups(db, product, spec.groups, products_by_name, ingredients_by_name)
        db.flush()


DEMO_ZONES = [("Centro", "5.00", 30), ("Vila Nova", "7.90", 40), ("Jardim America", "9.90", 45)]
DEMO_COURIERS = [("Carlos Moto", "(11) 98888-1111", "6.00"), ("Rafa Entregas", "(11) 97777-2222", "0")]
DEMO_COMMISSIONS = {"IFOOD": "23", "NINETY_NINE_FOOD": "18", "LOCAL": "0"}


def seed_store_extras(db: Session, establishment: Establishment) -> None:
    """Bairros, motoboys, comissoes, fidelidade e um cupom de exemplo. So cria o que falta."""
    for name, fee, minutes in DEMO_ZONES:
        if not db.scalar(select(DeliveryZone).where(DeliveryZone.establishment_id == establishment.id, DeliveryZone.name == name)):
            db.add(DeliveryZone(establishment_id=establishment.id, name=name, fee=Decimal(fee), estimated_minutes=minutes, active=True))
    if not db.scalar(select(Courier.id).where(Courier.establishment_id == establishment.id)):
        for name, phone, per_delivery in DEMO_COURIERS:
            db.add(Courier(establishment_id=establishment.id, name=name, phone=phone, fee_per_delivery=Decimal(per_delivery), active=True))
    if not establishment.channel_commissions:
        establishment.channel_commissions = dict(DEMO_COMMISSIONS)
    if not establishment.slug:
        establishment.slug = re.sub(r"[^a-z0-9]+", "-", establishment.name.lower()).strip("-")
    if establishment.whatsapp is None:
        # Primeira vez com cardapio online: usa o telefone da loja e deixa o link no ar
        establishment.whatsapp = re.sub(r"\D", "", establishment.phone or "") or None
        establishment.online_menu_enabled = True
    if not db.scalar(select(Coupon.id).where(Coupon.establishment_id == establishment.id)):
        db.add(Coupon(establishment_id=establishment.id, code="BEMVINDO10", kind="PERCENT", value=Decimal("10"), min_order=Decimal("30"), uses=0, active=True))
        # Primeira vez: liga a fidelidade de exemplo (a cada 10 pedidos, R$ 15 de desconto)
        establishment.loyalty_enabled = True
        establishment.loyalty_goal = 10
        establishment.loyalty_reward = Decimal("15.00")
    db.flush()


def order_lines(products: list[Product], index: int, rng: random.Random) -> list[OrderItemCreate]:
    selected = [products[index % len(products)], products[(index + 5) % len(products)]]
    if index % 3 == 0:
        selected.append(products[(index + 10) % len(products)])
    return [
        OrderItemCreate(product_id=product.id, quantity=1 + (index % 2), option_ids=pick_option_ids(product, rng))
        for product in selected
    ]


def seed_orders(db: Session, establishment: Establishment, slug: str) -> None:
    existing = db.scalar(
        select(Order).where(
            Order.establishment_id == establishment.id,
            Order.external_order_id == f"SEED-{slug}-0001",
        )
    )
    if existing:
        return

    products = [
        product
        for product in db.scalars(
            select(Product).where(Product.establishment_id == establishment.id, Product.is_available.is_(True)).order_by(Product.name)
        ).all()
        if can_be_ordered(product)
    ]
    random.seed(slug)
    rng = random.Random(slug)
    now = datetime.now(timezone.utc)
    sources = [
        OrderSource.IFOOD,
        OrderSource.NINETY_NINE_FOOD,
        OrderSource.OWN_DELIVERY,
        OrderSource.COUNTER,
        OrderSource.STORE_PICKUP,
    ]
    fulfillments = {
        OrderSource.IFOOD: FulfillmentType.DELIVERY,
        OrderSource.NINETY_NINE_FOOD: FulfillmentType.DELIVERY,
        OrderSource.OWN_DELIVERY: FulfillmentType.DELIVERY,
        OrderSource.COUNTER: FulfillmentType.COUNTER,
        OrderSource.STORE_PICKUP: FulfillmentType.PICKUP,
    }
    customers = ["Ana Martins", "Bruno Silva", "Carla Souza", "Daniel Alves", "Entrega rapida", "Mesa 03"]

    for index in range(SEED_ORDER_COUNT):
        source = sources[index % len(sources)]
        status, created_at = seed_timeline(index, now)
        payment_method = PaymentMethod.ONLINE if source in {OrderSource.IFOOD, OrderSource.NINETY_NINE_FOOD} else random.choice([PaymentMethod.PIX, PaymentMethod.CARD, PaymentMethod.CASH])
        payment_status = PaymentStatus.PAID if payment_method != PaymentMethod.CASH else PaymentStatus.PENDING
        order = create_order(
            db,
            establishment.id,
            source=source,
            external_order_id=f"SEED-{slug}-{index + 1:04d}",
            customer_name=customers[index % len(customers)],
            customer_phone=f"1199{index:04d}{index:02d}",
            delivery_address="Rua Demo, 123" if fulfillments[source] == FulfillmentType.DELIVERY else None,
            fulfillment_type=fulfillments[source],
            payment_method=payment_method,
            payment_status=payment_status,
            delivery_fee=Decimal("7.90") if fulfillments[source] == FulfillmentType.DELIVERY else Decimal("0.00"),
            discount=Decimal("0.00"),
            notes=random.choice([None, "Tocar a campainha", "Cliente pediu guardanapos extras", "Troco para R$ 100,00"]),
            lines=order_lines(products, index, rng),
            raw_payload={"seed": True},
        )
        order.created_at = created_at
        order.updated_at = min(created_at + timedelta(minutes=12), now)
        if status != OrderStatus.NEW:
            order.status = status
            add_event(
                db,
                order,
                "ORDER_STATUS_CHANGED",
                OrderStatus.NEW,
                status,
                {"seed": True, "cancel_reason": "Cliente desistiu" if status == OrderStatus.CANCELED else None},
            )
        for position, event in enumerate(order.events):
            event.created_at = min(created_at + timedelta(minutes=2 * position), now)
        db.commit()


def main() -> None:
    if get_settings().is_production:
        # Dados demo criam usuarios com a senha "demo123": nunca em producao.
        # Para o primeiro acesso em producao use: python -m scripts.create_admin
        raise SystemExit("Seed demo bloqueado em producao (ENVIRONMENT=production). Use scripts.create_admin.")
    with db_module.SessionLocal() as db:
        burger = get_or_create_establishment(
            db,
            "Burger Station",
            legal_name="Burger Station LTDA",
            tax_id="12.345.678/0001-90",
            phone="(11) 4002-8922",
            address="Rua das Fritas, 120 - Sao Paulo/SP",
            preparation_time=18,
        )
        smash = get_or_create_establishment(
            db,
            "Smash House",
            legal_name="Smash House Alimentos LTDA",
            tax_id="98.765.432/0001-10",
            phone="(11) 3030-4040",
            address="Av. Grelha Central, 445 - Sao Paulo/SP",
            preparation_time=22,
        )
        pizzaria = get_or_create_establishment(
            db,
            "Pizzaria Bella Massa",
            legal_name="Bella Massa Pizzas LTDA",
            tax_id="45.678.901/0001-23",
            phone="(11) 3232-5050",
            address="Rua do Forno, 88 - Sao Paulo/SP",
            preparation_time=35,
        )

        admin = get_or_create_user(db, "Admin Demo", "admin@comandahub.local")
        burger_user = get_or_create_user(db, "Atendimento Burger", "burger@comandahub.local")
        smash_user = get_or_create_user(db, "Atendimento Smash", "smash@comandahub.local")
        pizza_user = get_or_create_user(db, "Atendimento Pizzaria", "pizza@comandahub.local")
        kitchen = get_or_create_user(db, "Cozinha Demo", "cozinha@comandahub.local")

        for establishment in (burger, smash, pizzaria):
            ensure_membership(db, admin, establishment, UserRole.ADMIN)
            ensure_membership(db, kitchen, establishment, UserRole.KITCHEN)
        ensure_membership(db, burger_user, burger, UserRole.ATTENDANT)
        ensure_membership(db, smash_user, smash, UserRole.ATTENDANT)
        ensure_membership(db, pizza_user, pizzaria, UserRole.ATTENDANT)

        for establishment, slug, catalog in [
            (burger, "BURGER", BURGER_CATALOG),
            (smash, "SMASH", BURGER_CATALOG),
            (pizzaria, "PIZZA", PIZZA_CATALOG),
        ]:
            seed_catalog(db, establishment, catalog)
            seed_store_extras(db, establishment)
            db.commit()
            seed_orders(db, establishment, slug)

        db.commit()
        print("Seed concluido: usuarios demo, catalogos e pedidos foram preparados.")


if __name__ == "__main__":
    main()
