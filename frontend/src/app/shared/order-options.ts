import { OptionPricingMode, Product, ProductOption, ProductOptionGroup, SalesChannel, SelectedOption } from '../core/models';

export const CHANNELS: Array<{ id: SalesChannel; label: string; short: string }> = [
  { id: 'IFOOD', label: 'iFood', short: 'iFood' },
  { id: 'NINETY_NINE_FOOD', label: '99Food', short: '99' },
  { id: 'LOCAL', label: 'Local (balcao, retirada e delivery proprio)', short: 'Local' }
];

/** Mesmo nome de grupo que o backend usa para ingredientes em falta. */
export const MISSING_GROUP_NAME = 'Em falta';

export function channelShort(channel: SalesChannel): string {
  return CHANNELS.find((item) => item.id === channel)?.short ?? channel;
}

/** Preco do item no canal (ex.: mais caro no iFood); sem preco do canal vale o preco normal. */
export function priceFor(product: Product, channel: SalesChannel): number {
  const value = product.channel_prices?.[channel];
  return value !== undefined && value !== null ? Number(value) : Number(product.price);
}

/** Margem em % sobre o preco (0 se nao houver preco). */
export function marginPercent(price: number, cost: number): number {
  return price > 0 ? Math.round(((price - cost) / price) * 100) : 0;
}

export function isPausedOn(paused: SalesChannel[] | null | undefined, channel: SalesChannel): boolean {
  return (paused ?? []).includes(channel);
}

/** Por que o item nao pode ser vendido no canal (null = pode). Mesma regra do backend. */
export function productBlockReason(product: Product, channel: SalesChannel): string | null {
  if (!product.is_available) return 'Fora do cardapio';
  if (isPausedOn(product.paused_channels, channel)) return 'Pausado';
  const essential = (product.ingredients ?? []).find((item) => item.essential && isPausedOn(item.paused_channels, channel));
  return essential ? `Acabou ${essential.name}` : null;
}

export function optionAvailableOn(option: ProductOption, channel: SalesChannel): boolean {
  return option.is_available && !isPausedOn(option.paused_channels, channel);
}

/** Ingredientes que podem sair e estao em falta no canal: o item vai sem eles. */
export function missingIngredients(product: Product, channel: SalesChannel): string[] {
  return (product.ingredients ?? [])
    .filter((item) => !item.essential && isPausedOn(item.paused_channels, channel))
    .map((item) => item.name);
}

/** Mesmo retrato que o backend grava para ingrediente em falta ("Em falta: Sem Alface"). */
export function missingAsSelected(product: Product, channel: SalesChannel, chosen: SelectedOption[] = []): SelectedOption[] {
  const chosenNames = new Set(chosen.map((option) => option.name.trim().toLowerCase()));
  return missingIngredients(product, channel)
    .map((name) => `Sem ${name}`)
    .filter((label) => !chosenNames.has(label.toLowerCase()))
    .map((label) => ({ group_name: MISSING_GROUP_NAME, name: label, price_delta: '0.00', quantity: 1, notes: null }));
}

/** Grupos que aparecem com as escolhas atuais: um grupo condicional so aparece com a opcao que o libera. */
export function visibleGroups(product: Product, choices: CartChoice[]): ProductOptionGroup[] {
  const chosen = new Set(choices.map((choice) => choice.optionId));
  const groupOfOption = new Map<string, string>();
  for (const group of product.option_groups) {
    for (const option of group.options) groupOfOption.set(option.id, group.id);
  }
  const visibleIds = new Set<string>();
  const visible: ProductOptionGroup[] = [];
  for (const group of product.option_groups) {
    const trigger = group.depends_on_option_id;
    if (trigger && !(chosen.has(trigger) && visibleIds.has(groupOfOption.get(trigger) ?? ''))) continue;
    visibleIds.add(group.id);
    visible.push(group);
  }
  return visible;
}

/** Tira escolhas de grupos que sumiram (ex.: desmarcou "Fazer combo", sai a batata e a bebida). */
export function pruneHiddenChoices(product: Product, choices: CartChoice[]): CartChoice[] {
  let current = choices;
  for (;;) {
    const allowed = new Set(visibleGroups(product, current).flatMap((group) => group.options.map((option) => option.id)));
    const next = current.filter((choice) => allowed.has(choice.optionId));
    if (next.length === current.length) return next;
    current = next;
  }
}

/** Uma escolha feita na tela de personalizacao (antes de virar pedido). */
export interface CartChoice {
  optionId: string;
  quantity: number;
  notes: string;
}

export interface DisplayEntry {
  label: string;
  notes: string | null;
  /** "Sem cebola", "Sem molho"...: destacado para a cozinha nao passar batido */
  removal: boolean;
}

export interface DisplayGroup {
  /** Vazio em pedidos antigos, que nao guardavam o grupo */
  name: string;
  entries: DisplayEntry[];
}

const FRACTIONS: Record<number, string> = { 2: '1/2', 3: '1/3', 4: '1/4' };

export function roundCents(value: number): number {
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

export function isRemoval(name: string): boolean {
  return /^sem\s/i.test(name.trim());
}

/**
 * Agrupa as escolhas gravadas no item para exibir na comanda/cozinha:
 * "Bebida: Coca-Cola", "Adicionais: 2x Bacon extra", "Sabores: 1/2 Calabresa (sem cebola), 1/2 Mussarela".
 * Grupos cobrados pela mais cara ou pela media (pizza meio a meio) mostram a fracao.
 */
export function groupSelectedOptions(options: SelectedOption[] | null | undefined): DisplayGroup[] {
  const groups: Array<DisplayGroup & { split: boolean }> = [];
  for (const option of options ?? []) {
    const name = option.group_name ?? '';
    let group = groups.find((item) => item.name === name);
    if (!group) {
      group = { name, entries: [], split: option.pricing_mode === 'MAX' || option.pricing_mode === 'AVERAGE' };
      groups.push(group);
    }
    const quantity = option.quantity ?? 1;
    group.entries.push({
      label: quantity > 1 ? `${quantity}x ${option.name}` : option.name,
      notes: option.notes || null,
      removal: isRemoval(option.name)
    });
  }
  return groups.map(({ split, ...group }) => {
    const fraction = split ? FRACTIONS[group.entries.length] : undefined;
    if (!fraction) return group;
    return { ...group, entries: group.entries.map((entry) => ({ ...entry, label: `${fraction} ${entry.label}` })) };
  });
}

/** Converte as escolhas do carrinho no mesmo formato gravado no pedido (para exibir igual). */
export function choicesAsSelected(product: Product, choices: CartChoice[]): SelectedOption[] {
  const result: SelectedOption[] = [];
  for (const group of product.option_groups) {
    for (const option of group.options) {
      const choice = choices.find((item) => item.optionId === option.id);
      if (!choice) continue;
      result.push({
        option_id: option.id,
        group_id: group.id,
        group_name: group.name,
        pricing_mode: group.pricing_mode,
        name: option.name,
        price_delta: String(option.price_delta),
        quantity: choice.quantity,
        notes: choice.notes.trim() || null
      });
    }
  }
  return result;
}

/** Mesma regra do backend: SUM soma, MAX cobra a mais cara, AVERAGE cobra a media. O backend e quem decide o preco final. */
export function choicesPrice(product: Product, choices: CartChoice[]): number {
  let total = 0;
  for (const group of product.option_groups) {
    const picked = group.options
      .map((option) => ({ option, choice: choices.find((item) => item.optionId === option.id) }))
      .filter((item) => item.choice);
    if (!picked.length) continue;
    const deltas = picked.map((item) => Number(item.option.price_delta));
    const units = picked.map((item) => item.choice!.quantity);
    const weighted = deltas.reduce((sum, delta, index) => sum + delta * units[index], 0);
    if (group.pricing_mode === 'MAX') {
      total += Math.max(...deltas);
    } else if (group.pricing_mode === 'AVERAGE') {
      total += roundCents(weighted / units.reduce((sum, unit) => sum + unit, 0));
    } else {
      total += weighted;
    }
  }
  return roundCents(total);
}

export function groupUnits(group: ProductOptionGroup, choices: CartChoice[]): number {
  return group.options.reduce((sum, option) => sum + (choices.find((item) => item.optionId === option.id)?.quantity ?? 0), 0);
}

export function groupIsFull(group: ProductOptionGroup, choices: CartChoice[]): boolean {
  return group.max_choices > 0 && groupUnits(group, choices) >= group.max_choices;
}

export function groupRuleLabel(group: Pick<ProductOptionGroup, 'min_choices' | 'max_choices'>): string {
  const { min_choices: min, max_choices: max } = group;
  if (min > 0) {
    if (max === min) return `Obrigatorio - escolha ${min}`;
    if (max === 0) return `Obrigatorio - escolha pelo menos ${min}`;
    return `Obrigatorio - escolha de ${min} a ${max}`;
  }
  if (max === 0) return 'Opcional - escolha quantos quiser';
  return `Opcional - ate ${max}`;
}

export function pricingModeLabel(mode: OptionPricingMode): string {
  if (mode === 'MAX') return 'Cobra pela opcao mais cara';
  if (mode === 'AVERAGE') return 'Cobra a media das opcoes';
  return 'Soma as opcoes';
}

/** Mensagem de erro legivel: o FastAPI devolve texto ou uma lista de erros de validacao. */
export function errorMessage(err: unknown, fallback: string): string {
  const detail = (err as { error?: { detail?: unknown } })?.error?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => String((item as { msg?: string })?.msg ?? '').replace(/^Value error, /, ''))
      .filter(Boolean);
    if (messages.length) return messages.join(' | ');
  }
  return fallback;
}
