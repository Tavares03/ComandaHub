import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, input, model } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { LucideAngularModule } from 'lucide-angular';

import { Ingredient, OptionPricingMode, Product, ProductOptionGroup, ProductOptionGroupInput, SalesChannel } from '../../core/models';
import { channelShort, groupRuleLabel } from '../../shared/order-options';

export interface EditableOption {
  uid: number;
  /** Opcao ja salva: mantem o id e as pausas por canal ao salvar */
  id?: string;
  name: string;
  price_delta: number;
  is_available: boolean;
  linked_product_id: string | null;
  ingredient_id: string | null;
  /** Quanto do ingrediente a opcao gasta (Bacon extra = 0,03 kg) */
  ingredient_quantity: number;
  paused_channels: SalesChannel[];
}

export interface EditableGroup {
  uid: number;
  id?: string;
  name: string;
  min_choices: number;
  max_choices: number;
  pricing_mode: OptionPricingMode;
  allow_repeat: boolean;
  /** uid da opcao (de um grupo acima) que libera este grupo; null = sempre aparece */
  depends_on_uid: number | null;
  options: EditableOption[];
  open: boolean;
}

let uidSeq = 1;
const uid = () => uidSeq++;

type Template = Omit<ProductOptionGroupInput, 'options'> & { label: string; options: Array<[string, number]> };

/** Modelos prontos para comecar rapido; tudo pode ser editado depois. */
const TEMPLATES: Template[] = [
  { label: 'Ponto da carne', name: 'Ponto da carne', min_choices: 1, max_choices: 1, pricing_mode: 'SUM', allow_repeat: false,
    options: [['Mal passado', 0], ['Ao ponto', 0], ['Bem passado', 0]] },
  { label: 'Adicionais (pode repetir)', name: 'Adicionais', min_choices: 0, max_choices: 5, pricing_mode: 'SUM', allow_repeat: true,
    options: [['Carne extra', 9], ['Bacon extra', 5], ['Cheddar extra', 4]] },
  { label: 'Retirar ingredientes', name: 'Retirar ingredientes', min_choices: 0, max_choices: 0, pricing_mode: 'SUM', allow_repeat: false,
    options: [['Sem alface', 0], ['Sem tomate', 0], ['Sem cebola', 0], ['Sem molho', 0]] },
  { label: 'Sabores de pizza (meio a meio)', name: 'Sabores', min_choices: 1, max_choices: 2, pricing_mode: 'MAX', allow_repeat: false,
    options: [['Mussarela', 0], ['Calabresa', 0], ['Portuguesa', 6]] },
  { label: 'Borda de pizza', name: 'Borda', min_choices: 1, max_choices: 1, pricing_mode: 'SUM', allow_repeat: false,
    options: [['Borda tradicional', 0], ['Catupiry', 10], ['Cheddar', 10]] },
  { label: 'Tamanho', name: 'Tamanho', min_choices: 1, max_choices: 1, pricing_mode: 'SUM', allow_repeat: false,
    options: [['Pequeno', 0], ['Medio', 5], ['Grande', 10]] }
];

function blankOption(name = '', price = 0, linkedProductId: string | null = null): EditableOption {
  return { uid: uid(), name, price_delta: price, is_available: true, linked_product_id: linkedProductId, ingredient_id: null, ingredient_quantity: 0, paused_channels: [] };
}

/** keepIds=false ao copiar de outro produto: vira tudo novo neste produto. */
export function toEditableGroups(groups: ProductOptionGroup[], open = false, keepIds = true): EditableGroup[] {
  const uidByOptionId = new Map<string, number>();
  const editable = groups.map((group) => ({
    uid: uid(),
    id: keepIds ? group.id : undefined,
    name: group.name,
    min_choices: group.min_choices,
    max_choices: group.max_choices,
    pricing_mode: group.pricing_mode ?? 'SUM',
    allow_repeat: group.allow_repeat ?? false,
    depends_on_uid: null as number | null,
    open,
    options: group.options.map((option) => {
      const optionUid = uid();
      uidByOptionId.set(option.id, optionUid);
      return {
        uid: optionUid,
        id: keepIds ? option.id : undefined,
        name: option.name,
        price_delta: Number(option.price_delta),
        is_available: option.is_available,
        linked_product_id: option.linked_product_id ?? null,
        ingredient_id: option.ingredient_id ?? null,
        ingredient_quantity: Number(option.ingredient_quantity ?? 0),
        paused_channels: keepIds ? [...(option.paused_channels ?? [])] : []
      };
    })
  }));
  groups.forEach((group, index) => {
    if (group.depends_on_option_id) editable[index].depends_on_uid = uidByOptionId.get(group.depends_on_option_id) ?? null;
  });
  return editable;
}

/** Posicao (grupo, opcao) da opcao que libera o grupo, contando so os grupos acima dele. */
function dependencyRef(groups: EditableGroup[], index: number): { group: number; option: number } | null {
  const target = groups[index].depends_on_uid;
  if (target === null) return null;
  for (let groupIndex = 0; groupIndex < index; groupIndex++) {
    const optionIndex = groups[groupIndex].options.findIndex((option) => option.uid === target);
    if (optionIndex >= 0) return { group: groupIndex, option: optionIndex };
  }
  return null;
}

export function toGroupInputs(groups: EditableGroup[]): ProductOptionGroupInput[] {
  return groups.map((group, index) => ({
    id: group.id,
    name: group.name.trim(),
    min_choices: Number(group.min_choices) || 0,
    max_choices: Number(group.max_choices) || 0,
    pricing_mode: group.pricing_mode,
    allow_repeat: group.allow_repeat,
    depends_on: dependencyRef(groups, index),
    options: group.options.map((option) => ({
      id: option.id,
      name: option.name.trim(),
      price_delta: Number(option.price_delta) || 0,
      is_available: option.is_available,
      linked_product_id: option.linked_product_id,
      ingredient_id: option.ingredient_id,
      ingredient_quantity: option.ingredient_id ? Number(option.ingredient_quantity) || 0 : 0
    }))
  }));
}

/** Mesmas regras que o backend valida, para avisar antes de salvar. */
export function groupProblems(group: EditableGroup, all: EditableGroup[] = []): string[] {
  const problems: string[] = [];
  const min = Number(group.min_choices) || 0;
  const max = Number(group.max_choices) || 0;
  if (!group.name.trim()) problems.push('De um nome ao grupo');
  if (!group.options.length) problems.push('Adicione pelo menos uma opcao');
  if (group.options.some((option) => !option.name.trim())) problems.push('Toda opcao precisa de nome');
  if (group.options.some((option) => Number(option.price_delta) < 0)) problems.push('Preco nao pode ser negativo');
  if (min < 0 || max < 0) problems.push('Minimo e maximo nao podem ser negativos');
  if (max > 0 && min > max) problems.push('O minimo e maior que o maximo');
  const available = group.options.filter((option) => option.is_available).length;
  if (!group.allow_repeat && min > available) problems.push(`Exige ${min} escolha(s), mas so tem ${available} opcao(oes) disponivel(is)`);
  const index = all.indexOf(group);
  if (group.depends_on_uid !== null && index >= 0 && !dependencyRef(all, index)) {
    problems.push('A opcao que libera este grupo precisa estar num grupo acima dele');
  }
  return problems;
}

@Component({
  selector: 'app-option-groups-editor',
  standalone: true,
  imports: [CommonModule, FormsModule, LucideAngularModule],
  template: `
    <div class="space-y-3">
      <div>
        <h3 class="text-sm font-extrabold text-zinc-950">Personalizacao</h3>
        <p class="text-xs text-zinc-500">Escolhas que aparecem ao lancar o produto: ponto da carne, combo, adicionais, retirar ingredientes, sabores de pizza...</p>
      </div>

      @for (group of groups(); track group.uid; let index = $index; let first = $first; let last = $last) {
        <div class="rounded-lg border" [ngClass]="[problems(group).length ? 'border-red-300' : 'border-zinc-200', group.depends_on_uid !== null ? 'ml-3 border-l-4 border-l-brand-400' : '']">
          <div class="flex items-center gap-2 p-2.5">
            <button type="button" class="focus-ring min-w-0 flex-1 text-left" (click)="group.open = !group.open; touch()">
              <span class="block truncate text-sm font-extrabold text-zinc-900">{{ group.name || 'Grupo sem nome' }}</span>
              <span class="block truncate text-xs text-zinc-500">
                {{ ruleLabel(group) }} - {{ group.options.length }} opcao(oes){{ group.pricing_mode !== 'SUM' ? ' - ' + pricingShort(group.pricing_mode) : '' }}
              </span>
              @if (triggerLabel(group, index); as trigger) {
                <span class="block truncate text-xs font-bold text-brand-700">So aparece com: {{ trigger }}</span>
              }
            </button>
            <button type="button" class="focus-ring rounded p-1 text-zinc-500 hover:bg-zinc-100 disabled:opacity-30" [disabled]="first" (click)="move(index, -1)" aria-label="Subir grupo">
              <i-lucide name="chevron-up" [size]="16" />
            </button>
            <button type="button" class="focus-ring rounded p-1 text-zinc-500 hover:bg-zinc-100 disabled:opacity-30" [disabled]="last" (click)="move(index, 1)" aria-label="Descer grupo">
              <i-lucide name="chevron-down" [size]="16" />
            </button>
            <button type="button" class="focus-ring rounded p-1 text-red-600 hover:bg-red-50" (click)="removeGroup(index)" aria-label="Remover grupo">
              <i-lucide name="trash-2" [size]="15" />
            </button>
          </div>

          @if (group.open) {
            <div class="space-y-3 border-t border-zinc-100 p-3">
              <label class="block">
                <span class="mb-1 block text-xs font-bold text-zinc-500">Nome do grupo</span>
                <input class="focus-ring h-9 w-full rounded-md border border-zinc-200 px-2.5 text-sm" placeholder="Ex.: Ponto da carne"
                       [(ngModel)]="group.name" (ngModelChange)="touch()" />
              </label>
              <div class="grid grid-cols-2 gap-2">
                <label class="block">
                  <span class="mb-1 block text-xs font-bold text-zinc-500">Minimo</span>
                  <input class="focus-ring h-9 w-full rounded-md border border-zinc-200 px-2.5 text-sm" type="number" min="0"
                         [(ngModel)]="group.min_choices" (ngModelChange)="touch()" />
                </label>
                <label class="block">
                  <span class="mb-1 block text-xs font-bold text-zinc-500">Maximo (0 = sem limite)</span>
                  <input class="focus-ring h-9 w-full rounded-md border border-zinc-200 px-2.5 text-sm" type="number" min="0"
                         [(ngModel)]="group.max_choices" (ngModelChange)="touch()" />
                </label>
              </div>
              <p class="text-xs text-zinc-500">Minimo 1 deixa o grupo obrigatorio. Maximo 1 vira escolha unica.</p>
              <label class="block">
                <span class="mb-1 block text-xs font-bold text-zinc-500">Mostrar este grupo</span>
                <select class="focus-ring h-9 w-full rounded-md border border-zinc-200 bg-white px-2.5 text-sm"
                        [ngModel]="group.depends_on_uid" (ngModelChange)="group.depends_on_uid = $event; touch()">
                  <option [ngValue]="null">Sempre</option>
                  @for (trigger of triggerChoices(index); track trigger.uid) {
                    <option [ngValue]="trigger.uid">So quando escolher: {{ trigger.label }}</option>
                  }
                </select>
                <span class="mt-1 block text-xs text-zinc-500">Ex.: a bebida do combo so aparece quando escolhem "Fazer combo". O obrigatorio so vale quando o grupo aparece.</span>
              </label>
              <label class="block">
                <span class="mb-1 block text-xs font-bold text-zinc-500">Como cobrar as escolhas</span>
                <select class="focus-ring h-9 w-full rounded-md border border-zinc-200 bg-white px-2.5 text-sm"
                        [(ngModel)]="group.pricing_mode" (ngModelChange)="touch()">
                  <option value="SUM">Somar o preco de todas</option>
                  <option value="MAX">Cobrar so a mais cara (meio a meio)</option>
                  <option value="AVERAGE">Cobrar a media (meio a meio)</option>
                </select>
              </label>
              <label class="flex items-center gap-2 text-xs font-bold text-zinc-700">
                <input type="checkbox" [(ngModel)]="group.allow_repeat" (ngModelChange)="touch()" />
                Pode repetir a mesma opcao (ex.: 2x bacon)
              </label>

              <div class="space-y-2">
                <div class="grid grid-cols-[1fr_84px_auto_auto] items-center gap-1.5 text-[11px] font-bold uppercase text-zinc-400">
                  <span>Opcao</span><span>+ Preco</span><span title="Disponivel">Disp.</span><span></span>
                </div>
                @for (option of group.options; track option.uid; let optionIndex = $index) {
                  <div class="rounded-md bg-zinc-50 p-1.5">
                    <div class="grid grid-cols-[1fr_84px_auto_auto] items-center gap-1.5">
                      <input class="focus-ring h-8 min-w-0 rounded-md border border-zinc-200 bg-white px-2 text-sm" placeholder="Nome"
                             [(ngModel)]="option.name" (ngModelChange)="touch()" />
                      <input class="focus-ring h-8 min-w-0 rounded-md border border-zinc-200 bg-white px-2 text-sm" type="number" step="0.01" min="0"
                             [(ngModel)]="option.price_delta" (ngModelChange)="touch()" />
                      <input type="checkbox" class="mx-2" [(ngModel)]="option.is_available" (ngModelChange)="touch()" [attr.aria-label]="'Disponivel ' + option.name" />
                      <button type="button" class="focus-ring rounded p-1 text-red-600 hover:bg-red-50" (click)="removeOption(group, optionIndex)" aria-label="Remover opcao">
                        <i-lucide name="x" [size]="14" />
                      </button>
                    </div>
                    <div class="mt-1 flex flex-wrap items-center gap-1.5">
                      <i-lucide class="text-zinc-400" name="link" [size]="13" />
                      <select class="focus-ring h-7 min-w-0 flex-1 rounded-md border border-zinc-200 bg-white px-1.5 text-xs"
                              [attr.aria-label]="'Vinculo de ' + (option.name || 'opcao')"
                              [ngModel]="linkValue(option)" (ngModelChange)="setLink(option, $event)">
                        <option value="">Sem vinculo</option>
                        @if (linkProducts().length) {
                          <optgroup label="E este produto do cardapio">
                            @for (product of linkProducts(); track product.id) {
                              <option [value]="'p:' + product.id">{{ product.name }}</option>
                            }
                          </optgroup>
                        }
                        @if (ingredients().length) {
                          <optgroup label="Usa este ingrediente">
                            @for (ingredient of ingredients(); track ingredient.id) {
                              <option [value]="'i:' + ingredient.id">{{ ingredient.name }}</option>
                            }
                          </optgroup>
                        }
                      </select>
                      @if (option.ingredient_id) {
                        <label class="flex items-center gap-1" title="Quanto do ingrediente esta opcao gasta (0 para 'Sem ...')">
                          <input class="focus-ring h-7 w-20 rounded-md border border-zinc-200 bg-white px-1.5 text-xs" type="number" step="0.001" min="0"
                                 [(ngModel)]="option.ingredient_quantity" (ngModelChange)="touch()" [attr.aria-label]="'Quantidade gasta por ' + option.name" />
                          <span class="text-[11px] text-zinc-500">{{ unitOf(option.ingredient_id) }}</span>
                        </label>
                      }
                      @for (channel of option.paused_channels; track channel) {
                        <span class="rounded bg-red-50 px-1.5 py-0.5 text-[11px] font-bold text-red-700">Pausado {{ short(channel) }}</span>
                      }
                    </div>
                  </div>
                }
                <p class="text-[11px] text-zinc-500">Vinculo: ao pausar a Batata Frita "em todos os lugares", as opcoes ligadas a ela tambem saem.</p>
                <button type="button" class="focus-ring inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-bold text-brand-700 hover:bg-brand-50" (click)="addOption(group)">
                  <i-lucide name="plus" [size]="13" /> Opcao
                </button>
              </div>
            </div>
          }
          @if (problems(group).length) {
            <p class="border-t border-red-100 bg-red-50 px-3 py-2 text-xs font-bold text-red-700">{{ problems(group).join(' | ') }}</p>
          }
        </div>
      }

      <div class="grid gap-2">
        @if (!hasCombo()) {
          <button type="button" class="focus-ring inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-brand-200 bg-brand-50 text-sm font-bold text-brand-700 hover:bg-brand-100" (click)="addCombo()">
            <i-lucide name="shopping-bag" [size]="15" /> Permitir fazer combo (acompanhamento + bebida)
          </button>
        }
        <button type="button" class="focus-ring inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-dashed border-zinc-300 text-sm font-bold text-zinc-700 hover:bg-zinc-50" (click)="addBlank()">
          <i-lucide name="plus" [size]="15" /> Novo grupo em branco
        </button>
        <select class="focus-ring h-9 w-full rounded-lg border border-zinc-200 bg-white px-2.5 text-sm" (change)="addTemplate($any($event.target))" aria-label="Adicionar grupo a partir de um modelo">
          <option value="">+ Adicionar a partir de um modelo...</option>
          @for (template of templates; track template.label; let templateIndex = $index) {
            <option [value]="templateIndex">{{ template.label }}</option>
          }
        </select>
        @if (copySources().length) {
          <select class="focus-ring h-9 w-full rounded-lg border border-zinc-200 bg-white px-2.5 text-sm" (change)="copyFrom($any($event.target))" aria-label="Copiar grupos de outro produto">
            <option value="">+ Copiar grupos de outro produto...</option>
            @for (product of copySources(); track product.id) {
              <option [value]="product.id">{{ product.name }} ({{ product.option_groups.length }} grupo(s))</option>
            }
          </select>
        }
      </div>
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class OptionGroupsEditorComponent {
  readonly groups = model.required<EditableGroup[]>();
  /** Produtos com grupos que podem ser copiados (sem o que esta sendo editado) */
  readonly copySources = input<Product[]>([]);
  /** Produtos que uma opcao pode representar (batata e bebida do combo) */
  readonly linkProducts = input<Product[]>([]);
  readonly ingredients = input<Ingredient[]>([]);
  readonly templates = TEMPLATES;

  ruleLabel(group: EditableGroup): string {
    return groupRuleLabel({ min_choices: Number(group.min_choices) || 0, max_choices: Number(group.max_choices) || 0 });
  }

  pricingShort(mode: OptionPricingMode): string {
    return mode === 'MAX' ? 'cobra a mais cara' : 'cobra a media';
  }

  short(channel: SalesChannel): string {
    return channelShort(channel);
  }

  problems(group: EditableGroup): string[] {
    return groupProblems(group, this.groups());
  }

  hasCombo(): boolean {
    return this.groups().some((group) => group.depends_on_uid !== null);
  }

  /** Opcoes dos grupos acima que podem liberar o grupo da posicao index. */
  triggerChoices(index: number): Array<{ uid: number; label: string }> {
    return this.groups()
      .slice(0, index)
      .flatMap((group) => group.options.map((option) => ({ uid: option.uid, label: `${group.name || 'Grupo'} > ${option.name || 'opcao'}` })));
  }

  triggerLabel(group: EditableGroup, index: number): string | null {
    if (group.depends_on_uid === null) return null;
    return this.triggerChoices(index).find((choice) => choice.uid === group.depends_on_uid)?.label ?? 'opcao removida';
  }

  unitOf(ingredientId: string): string {
    return this.ingredients().find((item) => item.id === ingredientId)?.unit ?? '';
  }

  linkValue(option: EditableOption): string {
    if (option.linked_product_id) return `p:${option.linked_product_id}`;
    if (option.ingredient_id) return `i:${option.ingredient_id}`;
    return '';
  }

  setLink(option: EditableOption, value: string): void {
    option.linked_product_id = value.startsWith('p:') ? value.slice(2) : null;
    option.ingredient_id = value.startsWith('i:') ? value.slice(2) : null;
    const product = this.linkProducts().find((item) => item.id === option.linked_product_id);
    if (product && !option.name.trim()) option.name = product.name;
    this.touch();
  }

  /** Os campos editam os objetos direto; aqui avisamos o componente pai da mudanca. */
  touch(): void {
    this.groups.set([...this.groups()]);
  }

  addBlank(): void {
    this.groups.set([
      ...this.groups(),
      { uid: uid(), name: '', min_choices: 0, max_choices: 1, pricing_mode: 'SUM', allow_repeat: false, depends_on_uid: null, open: true,
        options: [blankOption()] }
    ]);
  }

  /**
   * Combo dentro do item: "Fazer combo" (opcional, com preco) libera acompanhamento e bebida obrigatorios.
   * As opcoes ja vem ligadas aos produtos das categorias de acompanhamentos e bebidas, se existirem.
   */
  addCombo(): void {
    const trigger = blankOption('Fazer combo (acompanhamento + bebida)', 18);
    const fromCategory = (pattern: RegExp, fallback: string[]) => {
      const products = this.linkProducts().filter((product) => pattern.test(product.category?.name ?? '') && product.is_available);
      return products.length
        ? products.map((product) => blankOption(product.name, 0, product.id))
        : fallback.map((name) => blankOption(name));
    };
    const base = { min_choices: 1, max_choices: 1, pricing_mode: 'SUM' as OptionPricingMode, allow_repeat: false, depends_on_uid: trigger.uid, open: true };
    this.groups.set([
      ...this.groups(),
      { uid: uid(), name: 'Combo', min_choices: 0, max_choices: 1, pricing_mode: 'SUM', allow_repeat: false, depends_on_uid: null, open: true, options: [trigger] },
      { ...base, uid: uid(), name: 'Acompanhamento do combo', options: fromCategory(/acompanh/i, ['Batata frita']) },
      { ...base, uid: uid(), name: 'Bebida do combo', options: fromCategory(/bebida/i, ['Refrigerante lata']) }
    ]);
  }

  addTemplate(select: HTMLSelectElement): void {
    const template = TEMPLATES[Number(select.value)];
    select.value = '';
    if (!template) return;
    const { label: _label, options, depends_on: _depends, ...settings } = template;
    this.groups.set([
      ...this.groups(),
      { ...settings, uid: uid(), open: true, depends_on_uid: null, options: options.map(([name, price]) => blankOption(name, price)) }
    ]);
  }

  copyFrom(select: HTMLSelectElement): void {
    const source = this.copySources().find((product) => product.id === select.value);
    select.value = '';
    if (!source) return;
    const existing = new Set(this.groups().map((group) => group.name.trim().toLowerCase()));
    const copies = toEditableGroups(source.option_groups, false, false).filter((group) => !existing.has(group.name.trim().toLowerCase()));
    // Grupo condicional cujo gatilho nao veio junto vira "sempre"
    const copiedUids = new Set(copies.flatMap((group) => group.options.map((option) => option.uid)));
    copies.forEach((group) => {
      if (group.depends_on_uid !== null && !copiedUids.has(group.depends_on_uid)) group.depends_on_uid = null;
    });
    this.groups.set([...this.groups(), ...copies]);
  }

  move(index: number, delta: number): void {
    const next = [...this.groups()];
    const [group] = next.splice(index, 1);
    next.splice(index + delta, 0, group);
    this.groups.set(next);
  }

  removeGroup(index: number): void {
    const group = this.groups()[index];
    if (group.options.some((option) => option.name.trim()) && !window.confirm(`Remover o grupo "${group.name || 'sem nome'}"?`)) return;
    const removed = new Set(group.options.map((option) => option.uid));
    this.groups().forEach((other) => {
      if (other.depends_on_uid !== null && removed.has(other.depends_on_uid)) other.depends_on_uid = null;
    });
    this.groups.set(this.groups().filter((_, position) => position !== index));
  }

  addOption(group: EditableGroup): void {
    group.options = [...group.options, blankOption()];
    this.touch();
  }

  removeOption(group: EditableGroup, index: number): void {
    const removed = group.options[index];
    this.groups().forEach((other) => {
      if (other.depends_on_uid === removed.uid) other.depends_on_uid = null;
    });
    group.options = group.options.filter((_, position) => position !== index);
    this.touch();
  }
}
