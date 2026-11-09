from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from typing import Annotated, Literal

from app.models.catalog import OptionPricingMode, SalesChannel
from app.schemas.common import ORMModel


class CategoryOut(ORMModel):
    id: str
    establishment_id: str
    name: str
    sort_order: int


class CategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    sort_order: int | None = None


class ProductOptionOut(ORMModel):
    id: str
    name: str
    price_delta: Decimal
    is_available: bool
    sort_order: int = 0
    paused_channels: list[SalesChannel] = []
    linked_product_id: str | None = None
    ingredient_id: str | None = None
    ingredient_quantity: Decimal = Decimal("0")


class ProductOptionGroupOut(ORMModel):
    id: str
    name: str
    min_choices: int
    max_choices: int
    sort_order: int = 0
    pricing_mode: OptionPricingMode = OptionPricingMode.SUM
    allow_repeat: bool = False
    depends_on_option_id: str | None = None
    options: list[ProductOptionOut] = []


class ProductOptionCreate(BaseModel):
    # Com id, a opcao existente e atualizada (mantem o id e as pausas por canal); sem id, e criada.
    id: str | None = None
    name: str = Field(min_length=1, max_length=120)
    price_delta: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=10, decimal_places=2)
    is_available: bool = True
    linked_product_id: str | None = None
    ingredient_id: str | None = None
    # Quanto do ingrediente a opcao gasta (Bacon extra = 0,03 kg)
    ingredient_quantity: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=3)


class OptionRef(BaseModel):
    """Posicao de uma opcao no proprio envio: grupo N, opcao M (contando do zero)."""

    group: int = Field(ge=0)
    option: int = Field(ge=0)


class ProductOptionGroupCreate(BaseModel):
    """A ordem da lista define a ordem de exibicao (dos grupos e das opcoes)."""

    id: str | None = None
    name: str = Field(min_length=1, max_length=120)
    min_choices: int = Field(default=0, ge=0, le=50)
    max_choices: int = Field(default=3, ge=0, le=50, description="0 = sem limite")
    pricing_mode: OptionPricingMode = OptionPricingMode.SUM
    allow_repeat: bool = False
    # Grupo condicional (ex.: bebida do combo so aparece com "Fazer combo"). Deve apontar para um grupo anterior.
    depends_on: OptionRef | None = None
    options: list[ProductOptionCreate] = Field(default_factory=list, max_length=60)

    @model_validator(mode="after")
    def validate_choices(self) -> "ProductOptionGroupCreate":
        if self.max_choices and self.min_choices > self.max_choices:
            raise ValueError(f"{self.name}: o minimo de escolhas nao pode ser maior que o maximo")
        if not self.options:
            raise ValueError(f"{self.name}: adicione pelo menos uma opcao ao grupo")
        available = sum(1 for option in self.options if option.is_available)
        if not self.allow_repeat and self.min_choices > available:
            raise ValueError(f"{self.name}: exige {self.min_choices} escolha(s), mas so tem {available} opcao(oes) disponivel(is)")
        return self


class ProductIngredientOut(BaseModel):
    ingredient_id: str
    name: str
    essential: bool
    quantity: Decimal = Decimal("0")
    unit: str = "un"
    paused_channels: list[SalesChannel] = []


class ProductIngredientIn(BaseModel):
    ingredient_id: str
    essential: bool = False
    # Ficha tecnica: quanto vai em uma unidade do item, na unidade do ingrediente
    quantity: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=3)


Price = Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2)]


class ProductOut(ORMModel):
    id: str
    establishment_id: str
    category_id: str
    name: str
    description: str | None = None
    price: Decimal
    image_url: str | None = None
    is_available: bool
    created_at: datetime
    updated_at: datetime
    paused_channels: list[SalesChannel] = []
    # Preco por canal; canal ausente usa price
    channel_prices: dict[SalesChannel, Decimal] = {}
    # Custo da ficha tecnica
    unit_cost: Decimal = Decimal("0")
    category: CategoryOut | None = None
    option_groups: list[ProductOptionGroupOut] = []
    ingredients: list[ProductIngredientOut] = []


class ProductCreate(BaseModel):
    category_id: str
    name: str = Field(min_length=2, max_length=140)
    description: str | None = None
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    image_url: str | None = None
    is_available: bool = True
    option_groups: list[ProductOptionGroupCreate] = []
    ingredients: list[ProductIngredientIn] = Field(default_factory=list, max_length=60)
    channel_prices: dict[SalesChannel, Price] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_dependencies(self) -> "ProductCreate":
        validate_group_dependencies(self.option_groups)
        return self


class ProductUpdate(BaseModel):
    category_id: str | None = None
    name: str | None = None
    description: str | None = None
    price: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    image_url: str | None = None
    is_available: bool | None = None
    option_groups: list[ProductOptionGroupCreate] | None = None
    ingredients: list[ProductIngredientIn] | None = Field(default=None, max_length=60)
    channel_prices: dict[SalesChannel, Price] | None = None

    @model_validator(mode="after")
    def validate_dependencies(self) -> "ProductUpdate":
        validate_group_dependencies(self.option_groups or [])
        return self


def validate_group_dependencies(groups: list[ProductOptionGroupCreate]) -> None:
    for index, group in enumerate(groups):
        ref = group.depends_on
        if ref is None:
            continue
        if ref.group >= index:
            raise ValueError(f"{group.name}: so pode depender de uma opcao de um grupo que aparece antes dele")
        if ref.option >= len(groups[ref.group].options):
            raise ValueError(f"{group.name}: a opcao de que ele depende nao existe")


IngredientUnit = Literal["un", "kg", "g", "L", "ml"]
Quantity = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=3)]
Cost = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=4)]


class IngredientOut(ORMModel):
    id: str
    establishment_id: str
    name: str
    unit: str = "un"
    # None = nao controla estoque
    stock_quantity: Decimal | None = None
    min_stock: Decimal | None = None
    cost_per_unit: Decimal = Decimal("0")
    # Estoque zerou e o sistema pausou sozinho; volta quando entrar mercadoria
    auto_paused: bool = False


class IngredientCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    unit: IngredientUnit = "un"
    stock_quantity: Quantity | None = None
    min_stock: Quantity | None = None
    cost_per_unit: Cost = Decimal("0")


class IngredientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    unit: IngredientUnit | None = None
    min_stock: Quantity | None = None
    cost_per_unit: Cost | None = None
    # False = parar de controlar o estoque (zera o saldo e tira as pausas automaticas)
    track_stock: bool | None = None


class StockEntry(BaseModel):
    """PURCHASE soma ao estoque (chegou mercadoria). ADJUST troca pelo valor contado."""

    kind: Literal["PURCHASE", "ADJUST"]
    quantity: Quantity
    # Na compra, atualiza o custo do ingrediente
    unit_cost: Cost | None = None
    note: str | None = Field(default=None, max_length=200)


class StockMovementOut(ORMModel):
    id: str
    reason: str
    delta: Decimal
    balance: Decimal
    order_id: str | None = None
    unit_cost: Decimal | None = None
    note: str | None = None
    created_at: datetime


class ChannelPriceBulk(BaseModel):
    """Define o preco de um canal a partir do preco normal + percentual. percent=None tira o preco do canal."""

    channel: SalesChannel
    percent: Annotated[Decimal, Field(ge=-90, le=500)] | None = None
    round_to_90: bool = False
    # Vazio = todos os itens da loja
    product_ids: list[str] = Field(default_factory=list, max_length=500)


class AvailabilityChange(BaseModel):
    product_name: str
    what: str


class AvailabilityStoreResult(BaseModel):
    establishment_id: str
    establishment_name: str
    changes: list[AvailabilityChange] = []


class AvailabilityRequest(BaseModel):
    """Pausar ou reativar um item ou ingrediente em alguns canais.

    scope (item): "item" = so o item; "everywhere" = o item e as opcoes de outros itens ligadas a ele (combos).
    scope (ingrediente): "everywhere" = todos os itens que usam; "selected" = so os itens de product_ids.
    """

    target_type: Literal["product", "ingredient"]
    target_id: str
    action: Literal["pause", "resume"]
    channels: list[SalesChannel] = Field(min_length=1)
    scope: Literal["item", "everywhere", "selected"] = "item"
    product_ids: list[str] = Field(default_factory=list, max_length=200)
    all_establishments: bool = False
    dry_run: bool = False


class AvailabilityResponse(BaseModel):
    results: list[AvailabilityStoreResult]
    # Lojas em que nao existe item/ingrediente com o mesmo nome
    not_found_in: list[str] = []
