"""Escolhas aleatorias porem validas para pedidos gerados (simulador e seed)."""
from __future__ import annotations

import random

from app.models.catalog import Product, ProductOption, ProductOptionGroup, SalesChannel
from app.services.availability import option_is_available, product_block_reason


def _available(group: ProductOptionGroup, channel: SalesChannel | str | None) -> list[ProductOption]:
    return [option for option in group.options if option_is_available(option, channel)]


def _can_fill(group: ProductOptionGroup, channel: SalesChannel | str | None) -> bool:
    available = len(_available(group, channel))
    if not group.min_choices:
        return True
    return available > 0 and (group.allow_repeat or available >= group.min_choices)


def can_be_ordered(product: Product, channel: SalesChannel | str | None = None) -> bool:
    """False quando o item esta pausado no canal ou algum grupo obrigatorio nao tem opcoes suficientes.

    Grupos condicionais (ex.: bebida do combo) so contam se o cliente escolher a opcao que os libera.
    """
    if product_block_reason(product, channel):
        return False
    return all(_can_fill(group, channel) for group in product.option_groups if not group.depends_on_option_id)


def pick_option_ids(
    product: Product,
    rng: random.Random,
    extra_chance: float = 0.35,
    channel: SalesChannel | str | None = None,
) -> list[str]:
    """Cumpre o minimo de cada grupo e, as vezes, escolhe uma opcao a mais (sem passar do maximo).

    Pula grupos condicionais cuja opcao-gatilho nao foi escolhida e nunca escolhe um gatilho
    (ex.: "Fazer combo") se algum grupo que ele libera nao puder ser preenchido.
    """
    dependents: dict[str, list[ProductOptionGroup]] = {}
    for group in product.option_groups:
        if group.depends_on_option_id:
            dependents.setdefault(group.depends_on_option_id, []).append(group)

    picked: set[str] = set()
    option_ids: list[str] = []
    for group in product.option_groups:
        if group.depends_on_option_id and group.depends_on_option_id not in picked:
            continue
        available = [
            option for option in _available(group, channel)
            if all(_can_fill(dependent, channel) for dependent in dependents.get(option.id, []))
        ]
        if not available:
            continue
        limit = group.max_choices or len(available)
        if not group.allow_repeat:
            limit = min(limit, len(available))
        count = min(group.min_choices, limit)
        if count < limit and rng.random() < extra_chance:
            count += 1
        if group.allow_repeat:
            picks = [rng.choice(available) for _ in range(count)]
        else:
            picks = rng.sample(available, count)
        option_ids.extend(option.id for option in picks)
        picked.update(option.id for option in picks)
    return option_ids
