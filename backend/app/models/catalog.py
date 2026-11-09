from __future__ import annotations

from decimal import Decimal
from enum import Enum

from datetime import datetime

from sqlalchemy import JSON, Boolean, Enum as SAEnum, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin, UTCDateTime


class OptionPricingMode(str, Enum):
    """Como o preco das escolhas de um grupo entra no item.

    SUM: soma tudo (adicionais). MAX: cobra so a escolha mais cara (pizza meio a meio
    pelo sabor mais caro). AVERAGE: cobra a media das escolhas (meio a meio pela media).
    """

    SUM = "SUM"
    MAX = "MAX"
    AVERAGE = "AVERAGE"


class SalesChannel(str, Enum):
    """Onde o item e vendido. LOCAL cobre balcao, retirada e delivery proprio."""

    IFOOD = "IFOOD"
    NINETY_NINE_FOOD = "NINETY_NINE_FOOD"
    LOCAL = "LOCAL"


class Category(Base, IdMixin):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("establishment_id", "name", name="uq_category_establishment_name"),)

    establishment_id: Mapped[str] = mapped_column(ForeignKey("establishments.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    establishment = relationship("Establishment", back_populates="categories")
    products = relationship("Product", back_populates="category")


class Product(Base, IdMixin, TimestampMixin):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("establishment_id", "name", name="uq_product_establishment_name"),)

    establishment_id: Mapped[str] = mapped_column(ForeignKey("establishments.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(140))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    # Preco por canal, ex.: {"IFOOD": "36.90"}. Canal sem preco usa o campo price.
    channel_prices: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, server_default="{}")
    # Canais (SalesChannel) em que o item esta pausado, ex.: ["NINETY_NINE_FOOD"]. Sempre atribua uma lista nova.
    paused_channels: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")

    establishment = relationship("Establishment", back_populates="products")
    category = relationship("Category", back_populates="products")
    ingredient_links = relationship(
        "ProductIngredient",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductIngredient.sort_order",
    )
    option_groups = relationship(
        "ProductOptionGroup",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by=lambda: [ProductOptionGroup.sort_order, ProductOptionGroup.name],
    )

    @property
    def unit_cost(self) -> Decimal:
        """Custo da ficha tecnica (quantidade x custo de cada ingrediente)."""
        total = sum(
            (Decimal(link.quantity or 0) * Decimal(link.ingredient.cost_per_unit or 0) for link in self.ingredient_links),
            Decimal("0"),
        )
        return total.quantize(Decimal("0.01"))

    @property
    def ingredients(self) -> list[dict]:
        """Ingredientes do item no formato da API (nome vem do cadastro de ingredientes)."""
        return [
            {
                "ingredient_id": link.ingredient_id,
                "name": link.ingredient.name,
                "essential": link.essential,
                "quantity": link.quantity,
                "unit": link.ingredient.unit,
                "paused_channels": list(link.paused_channels or []),
            }
            for link in self.ingredient_links
        ]


class ProductOptionGroup(Base, IdMixin):
    __tablename__ = "product_option_groups"

    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    min_choices: Mapped[int] = mapped_column(Integer, default=0)
    # 0 = sem limite
    max_choices: Mapped[int] = mapped_column(Integer, default=3)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    pricing_mode: Mapped[OptionPricingMode] = mapped_column(
        SAEnum(OptionPricingMode, native_enum=False, length=16),
        default=OptionPricingMode.SUM,
        server_default=OptionPricingMode.SUM.value,
    )
    # Permite escolher a mesma opcao mais de uma vez (ex.: 2x carne extra)
    allow_repeat: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # Grupo condicional: so aparece (e so e exigido) quando esta opcao de um grupo anterior foi escolhida.
    # Ex.: "Bebida do combo" depende de "Fazer combo". Sem FK para nao criar ciclo grupos <-> opcoes.
    depends_on_option_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    product = relationship("Product", back_populates="option_groups")
    options = relationship(
        "ProductOption",
        back_populates="group",
        cascade="all, delete-orphan",
        order_by=lambda: [ProductOption.sort_order, ProductOption.name],
    )


class ProductOption(Base, IdMixin):
    __tablename__ = "product_options"

    group_id: Mapped[str] = mapped_column(ForeignKey("product_option_groups.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    price_delta: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    paused_channels: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    # A opcao "e" um produto do cardapio (batata do combo = produto Batata Frita) ou usa um ingrediente.
    # Serve para pausar em cascata: tirar a batata do cardapio tambem tira dos combos.
    linked_product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True)
    ingredient_id: Mapped[str | None] = mapped_column(ForeignKey("ingredients.id", ondelete="SET NULL"), nullable=True, index=True)
    # Quanto do ingrediente a opcao gasta (ex.: Bacon extra = 0,03 kg). "Sem alface" fica com 0.
    ingredient_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("0"), server_default="0")

    group = relationship("ProductOptionGroup", back_populates="options")
    linked_product = relationship("Product", foreign_keys=[linked_product_id])


class Ingredient(Base, IdMixin):
    """Insumo usado nos itens (alface, batata, bacon...). Serve para pausar tudo que leva ele."""

    __tablename__ = "ingredients"
    __table_args__ = (UniqueConstraint("establishment_id", "name", name="uq_ingredient_establishment_name"),)

    establishment_id: Mapped[str] = mapped_column(ForeignKey("establishments.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    # Unidade das quantidades (un, kg, g, L, ml). Nao ha conversao: a ficha tecnica usa a mesma unidade.
    unit: Mapped[str] = mapped_column(String(8), default="un", server_default="un")
    # None = nao controla estoque deste ingrediente
    stock_quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    min_stock: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    cost_per_unit: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0"), server_default="0")
    # Canais pausados automaticamente quando o estoque zerou (voltam sozinhos quando chega mercadoria)
    auto_paused_channels: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")

    product_links = relationship("ProductIngredient", back_populates="ingredient", cascade="all, delete-orphan")

    @property
    def auto_paused(self) -> bool:
        return bool(self.auto_paused_channels)


class ProductIngredient(Base, IdMixin):
    """Ingrediente de um item. A pausa fica aqui para poder tirar o alface so de alguns itens.

    essential=True: sem ele o item sai do cardapio (batata na Batata Frita).
    essential=False: o item continua a venda, so que sem ele (alface no hamburguer).
    """

    __tablename__ = "product_ingredients"
    __table_args__ = (UniqueConstraint("product_id", "ingredient_id", name="uq_product_ingredient"),)

    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    ingredient_id: Mapped[str] = mapped_column(ForeignKey("ingredients.id", ondelete="CASCADE"), index=True)
    essential: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # Quanto do ingrediente vai em uma unidade do item (ficha tecnica), na unidade do ingrediente
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("0"), server_default="0")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    paused_channels: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")

    product = relationship("Product", back_populates="ingredient_links")
    ingredient = relationship("Ingredient", back_populates="product_links")


class StockMovement(Base, IdMixin):
    """Historico do estoque: baixa por pedido, devolucao por cancelamento, compra e contagem."""

    __tablename__ = "stock_movements"
    __table_args__ = (Index("ix_stock_movements_ingredient_created", "ingredient_id", "created_at"),)

    establishment_id: Mapped[str] = mapped_column(ForeignKey("establishments.id", ondelete="CASCADE"), index=True)
    ingredient_id: Mapped[str] = mapped_column(ForeignKey("ingredients.id", ondelete="CASCADE"))
    # ORDER (baixa), CANCEL (devolucao), PURCHASE (entrada), ADJUST (contagem)
    reason: Mapped[str] = mapped_column(String(16))
    delta: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True)
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
