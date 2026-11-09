import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, HostListener, OnInit, computed, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { LucideAngularModule } from 'lucide-angular';

import { Product, ProductOption, ProductOptionGroup, SalesChannel, SelectedOption } from '../../core/models';
import { ItemOptionsComponent } from '../../shared/item-options.component';
import {
  CartChoice,
  choicesAsSelected,
  choicesPrice,
  groupIsFull,
  groupRuleLabel,
  groupUnits,
  missingAsSelected,
  missingIngredients,
  optionAvailableOn,
  priceFor,
  pricingModeLabel,
  pruneHiddenChoices,
  roundCents,
  visibleGroups
} from '../../shared/order-options';

export interface CustomizedItem {
  choices: CartChoice[];
  notes: string;
  quantity: number;
}

/** Janela de personalizacao de um item: ponto, adicionais, retirar, combo, sabores de pizza... */
@Component({
  selector: 'app-item-customizer',
  standalone: true,
  imports: [CommonModule, FormsModule, LucideAngularModule, ItemOptionsComponent],
  template: `
    <div class="fixed inset-0 z-50 bg-zinc-950/50" (click)="closed.emit()"></div>
    <section
      class="fixed inset-0 z-50 flex flex-col overflow-hidden bg-zinc-50 shadow-2xl lg:inset-4 lg:rounded-2xl"
      role="dialog"
      aria-modal="true"
      [attr.aria-label]="'Personalizar ' + product().name"
    >
      <header class="flex items-start justify-between gap-4 border-b border-zinc-200 bg-white px-5 py-4">
        <div class="min-w-0">
          <p class="text-xs font-bold uppercase text-brand-600">{{ editing() ? 'Editar item' : 'Personalizar item' }}</p>
          <div class="flex flex-wrap items-baseline gap-x-3">
            <h2 class="text-2xl font-extrabold text-zinc-950">{{ product().name }}</h2>
            <span class="text-base font-bold text-zinc-600">{{ basePrice() | currency:'BRL':'symbol':'1.2-2' }}</span>
          </div>
          @if (product().description) {
            <p class="mt-0.5 text-sm text-zinc-500">{{ product().description }}</p>
          }
        </div>
        <button type="button" class="focus-ring rounded-md border border-zinc-200 bg-white p-2 hover:bg-zinc-50" (click)="closed.emit()" aria-label="Fechar">
          <i-lucide name="x" [size]="20" />
        </button>
      </header>

      <div class="flex min-h-0 flex-1 flex-col lg:flex-row">
        <div class="min-h-0 flex-1 space-y-4 overflow-y-auto p-4 lg:p-5">
          @if (missingNow().length) {
            <p class="flex items-start gap-2 rounded-lg bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-900">
              <i-lucide class="mt-0.5 shrink-0" name="triangle-alert" [size]="16" />
              Em falta hoje: vai sem {{ missingNow().join(', ') }}.
            </p>
          }

          <div class="grid items-start gap-3 min-[1700px]:grid-cols-2">
            @for (group of groups(); track group.id) {
              <fieldset
                class="rounded-xl border bg-white p-4"
                [ngClass]="[
                  missing(group) && triedSubmit() ? 'border-red-300 bg-red-50/40' : 'border-zinc-200',
                  group.depends_on_option_id ? 'border-l-4 border-l-brand-400' : ''
                ]"
              >
                <legend class="sr-only">{{ group.name }}</legend>
                <div class="flex items-start justify-between gap-2">
                  <div class="flex min-w-0 flex-1 flex-wrap items-baseline gap-x-2">
                    <h3 class="text-base font-extrabold text-zinc-950">{{ group.name }}</h3>
                    <p class="text-xs font-semibold text-zinc-500">
                      {{ ruleLabel(group) }}
                      @if (group.pricing_mode !== 'SUM') { - {{ pricingLabel(group) }} }
                      @if (triggerName(group); as trigger) { - parte de: {{ trigger }} }
                    </p>
                  </div>
                  <span
                    class="shrink-0 rounded-full px-2.5 py-1 text-xs font-extrabold"
                    [ngClass]="missing(group) ? 'bg-amber-100 text-amber-800' : 'bg-emerald-50 text-emerald-700'"
                  >
                    {{ units(group) }}{{ group.max_choices ? '/' + group.max_choices : '' }}
                  </span>
                </div>

                <div class="mt-2.5 grid grid-cols-[repeat(auto-fill,minmax(170px,1fr))] gap-2">
                  @for (option of group.options; track option.id) {
                    <div
                      class="relative flex flex-col rounded-lg border transition"
                      [ngClass]="quantityOf(option) ? 'border-brand-500 bg-brand-50/60' : 'border-zinc-200 hover:border-zinc-300'"
                      [class.opacity-50]="!available(option)"
                    >
                      @if (group.allow_repeat) {
                        <div class="flex-1 p-3">
                          <p class="break-words text-sm font-bold leading-snug text-zinc-900">{{ option.name }}</p>
                          <p class="text-xs text-zinc-500">
                            @if (!available(option)) { Indisponivel }
                            @else if (delta(option) > 0) { + {{ delta(option) | currency:'BRL':'symbol':'1.2-2' }} }
                            @else { Sem custo }
                          </p>
                          <div class="mt-2 flex items-center gap-1">
                            <button type="button" class="focus-ring rounded-md border border-zinc-200 bg-white p-2 disabled:opacity-40"
                                    [disabled]="!quantityOf(option)" (click)="decrement(option)" [attr.aria-label]="'Menos ' + option.name">
                              <i-lucide name="minus" [size]="14" />
                            </button>
                            <span class="w-7 text-center text-sm font-extrabold">{{ quantityOf(option) }}</span>
                            <button type="button" class="focus-ring rounded-md border border-zinc-200 bg-white p-2 disabled:opacity-40"
                                    [disabled]="!available(option) || isFull(group)" (click)="increment(group, option)" [attr.aria-label]="'Mais ' + option.name">
                              <i-lucide name="plus" [size]="14" />
                            </button>
                          </div>
                        </div>
                      } @else {
                        <button
                          type="button"
                          class="focus-ring flex w-full flex-1 items-start gap-3 rounded-lg p-3 text-left disabled:cursor-not-allowed"
                          [disabled]="!available(option) || (!quantityOf(option) && isFull(group) && group.max_choices !== 1)"
                          (click)="toggle(group, option)"
                        >
                          <span
                            class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center border-2"
                            [ngClass]="[
                              group.max_choices === 1 ? 'rounded-full' : 'rounded',
                              quantityOf(option) ? 'border-brand-500 bg-brand-500 text-white' : 'border-zinc-300 bg-white'
                            ]"
                          >
                            @if (quantityOf(option)) { <i-lucide name="check" [size]="12" /> }
                          </span>
                          <span class="min-w-0 flex-1">
                            <span class="block break-words text-sm font-bold leading-snug text-zinc-900">{{ option.name }}</span>
                            <span class="block text-xs text-zinc-500">
                              @if (!available(option)) { Indisponivel }
                              @else if (delta(option) > 0) { + {{ delta(option) | currency:'BRL':'symbol':'1.2-2' }} }
                              @else { Sem custo }
                            </span>
                          </span>
                        </button>
                      }
                      @if (quantityOf(option)) {
                        <button type="button" class="focus-ring absolute bottom-1.5 right-1.5 rounded-md p-1.5 text-zinc-500 hover:bg-white hover:text-zinc-800"
                                [class.text-brand-700]="noteOf(option)"
                                (click)="toggleNote(option)" [attr.aria-label]="'Observacao para ' + option.name" title="Observacao">
                          <i-lucide name="message-square" [size]="15" />
                        </button>
                      }
                      @if (quantityOf(option) && noteOpen(option)) {
                        <div class="pb-3 pl-3 pr-10">
                          <input
                            class="focus-ring h-9 w-full rounded-md border border-zinc-200 bg-white px-3 text-sm"
                            maxlength="120"
                            [placeholder]="'Obs. ' + option.name"
                            [ngModel]="noteOf(option)"
                            (ngModelChange)="setNote(option, $event)"
                          />
                        </div>
                      }
                    </div>
                  }
                </div>
              </fieldset>
            }
          </div>

          <label class="block lg:hidden">
            <span class="mb-1 block text-sm font-extrabold text-zinc-950">Observacao do item</span>
            <textarea
              class="focus-ring min-h-20 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm"
              maxlength="300"
              placeholder="Ex.: cortar ao meio, caprichar no molho, bem gelada"
              [ngModel]="notes()"
              (ngModelChange)="notes.set($event)"
            ></textarea>
          </label>
        </div>

        <aside class="flex shrink-0 flex-col border-t border-zinc-200 bg-white lg:w-80 lg:border-l 2xl:w-96 lg:border-t-0">
          <div class="hidden min-h-0 flex-1 space-y-4 overflow-y-auto p-5 lg:block">
            <div>
              <h3 class="text-sm font-extrabold uppercase tracking-wide text-zinc-500">Resumo do item</h3>
              <p class="mt-2 text-lg font-extrabold text-zinc-950">{{ quantity() }}x {{ product().name }}</p>
              <div class="mt-1">
                <app-item-options [options]="summary()" />
                @if (!summary().length) {
                  <p class="text-sm text-zinc-400">Nada escolhido ainda.</p>
                }
              </div>
            </div>

            @if (problems().length) {
              <div class="rounded-lg px-3 py-2 text-sm font-bold" [ngClass]="triedSubmit() ? 'bg-red-50 text-red-700' : 'bg-amber-50 text-amber-800'">
                Falta escolher: {{ problems().join(', ') }}
              </div>
            }

            <label class="block">
              <span class="mb-1 block text-sm font-extrabold text-zinc-950">Observacao do item</span>
              <textarea
                class="focus-ring min-h-28 w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm"
                maxlength="300"
                placeholder="Ex.: cortar ao meio, caprichar no molho, bem gelada"
                [ngModel]="notes()"
                (ngModelChange)="notes.set($event)"
              ></textarea>
            </label>

            <div class="space-y-1 border-t border-zinc-100 pt-3 text-sm">
              <div class="flex justify-between text-zinc-500"><span>Preco unitario</span><span>{{ unitPrice() | currency:'BRL':'symbol':'1.2-2' }}</span></div>
              <div class="flex justify-between text-base font-extrabold text-zinc-950"><span>Total</span><span>{{ total() | currency:'BRL':'symbol':'1.2-2' }}</span></div>
            </div>
          </div>

          <div class="border-t border-zinc-100 p-4">
            @if (triedSubmit() && problems().length) {
              <p class="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm font-bold text-red-700 lg:hidden">Falta escolher: {{ problems().join(', ') }}</p>
            }
            <div class="flex items-center gap-3 lg:flex-col lg:items-stretch">
              <div class="flex items-center gap-1 lg:justify-between">
                <span class="hidden text-sm font-bold text-zinc-600 lg:block">Quantidade</span>
                <div class="flex items-center gap-1">
                  <button type="button" class="focus-ring rounded-md border border-zinc-200 p-3 disabled:opacity-40" [disabled]="quantity() <= 1"
                          (click)="quantity.set(quantity() - 1)" aria-label="Diminuir quantidade">
                    <i-lucide name="minus" [size]="16" />
                  </button>
                  <span class="w-9 text-center text-lg font-extrabold">{{ quantity() }}</span>
                  <button type="button" class="focus-ring rounded-md border border-zinc-200 p-3 disabled:opacity-40" [disabled]="quantity() >= 99"
                          (click)="quantity.set(quantity() + 1)" aria-label="Aumentar quantidade">
                    <i-lucide name="plus" [size]="16" />
                  </button>
                </div>
              </div>
              <button type="button" class="focus-ring inline-flex h-12 flex-1 items-center justify-between gap-3 rounded-lg bg-brand-500 px-4 text-sm font-extrabold text-white hover:bg-brand-600 lg:flex-none"
                      (click)="confirm()">
                <span class="whitespace-nowrap">{{ editing() ? 'Salvar item' : 'Adicionar' }}<span class="hidden sm:inline">{{ editing() ? '' : ' a comanda' }}</span></span>
                <span>{{ total() | currency:'BRL':'symbol':'1.2-2' }}</span>
              </button>
            </div>
          </div>
        </aside>
      </div>
    </section>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class ItemCustomizerComponent implements OnInit {
  readonly product = input.required<Product>();
  /** Item ja no carrinho (editar) ou null (adicionar novo) */
  readonly initial = input<CustomizedItem | null>(null);
  /** Canal do pedido: opcoes pausadas nele aparecem como indisponiveis */
  readonly channel = input<SalesChannel>('LOCAL');
  readonly confirmed = output<CustomizedItem>();
  readonly closed = output<void>();

  readonly choices = signal<CartChoice[]>([]);
  readonly notes = signal('');
  readonly quantity = signal(1);
  readonly openNotes = signal<Set<string>>(new Set());
  readonly triedSubmit = signal(false);

  readonly editing = computed(() => this.initial() !== null);
  /** So os grupos liberados pelas escolhas atuais (a bebida do combo so aparece com "Fazer combo") */
  readonly groups = computed(() => visibleGroups(this.product(), this.choices()));
  readonly missingNow = computed(() => missingIngredients(this.product(), this.channel()));
  /** O que vai para a comanda, igual a cozinha vai ver (inclui "Em falta: Sem Alface") */
  readonly summary = computed<SelectedOption[]>(() => {
    const selected = choicesAsSelected(this.product(), this.choices());
    return [...selected, ...missingAsSelected(this.product(), this.channel(), selected)];
  });
  readonly basePrice = computed(() => priceFor(this.product(), this.channel()));
  readonly unitPrice = computed(() => roundCents(this.basePrice() + choicesPrice(this.product(), this.choices())));
  readonly total = computed(() => roundCents(this.unitPrice() * this.quantity()));
  readonly problems = computed(() =>
    this.groups()
      .filter((group) => groupUnits(group, this.choices()) < group.min_choices)
      .map((group) => group.name)
  );

  ngOnInit(): void {
    const initial = this.initial();
    if (initial) {
      this.choices.set(initial.choices.map((choice) => ({ ...choice })));
      this.notes.set(initial.notes);
      this.quantity.set(initial.quantity);
      this.openNotes.set(new Set(initial.choices.filter((choice) => choice.notes).map((choice) => choice.optionId)));
    }
  }

  @HostListener('document:keydown.escape')
  onEscape(): void {
    this.closed.emit();
  }

  units(group: ProductOptionGroup): number {
    return groupUnits(group, this.choices());
  }

  isFull(group: ProductOptionGroup): boolean {
    return groupIsFull(group, this.choices());
  }

  missing(group: ProductOptionGroup): boolean {
    return this.units(group) < group.min_choices;
  }

  ruleLabel(group: ProductOptionGroup): string {
    return groupRuleLabel(group);
  }

  pricingLabel(group: ProductOptionGroup): string {
    return pricingModeLabel(group.pricing_mode);
  }

  /** Nome da opcao que libera o grupo (ex.: "Fazer combo"), para marcar os grupos do combo. */
  triggerName(group: ProductOptionGroup): string | null {
    if (!group.depends_on_option_id) return null;
    for (const other of this.product().option_groups) {
      const option = other.options.find((item) => item.id === group.depends_on_option_id);
      if (option) return option.name;
    }
    return null;
  }

  available(option: ProductOption): boolean {
    return optionAvailableOn(option, this.channel());
  }

  delta(option: ProductOption): number {
    return Number(option.price_delta);
  }

  quantityOf(option: ProductOption): number {
    return this.choices().find((choice) => choice.optionId === option.id)?.quantity ?? 0;
  }

  noteOf(option: ProductOption): string {
    return this.choices().find((choice) => choice.optionId === option.id)?.notes ?? '';
  }

  noteOpen(option: ProductOption): boolean {
    return this.openNotes().has(option.id);
  }

  /** Grupo de 1 escolha funciona como radio; os demais como checkbox. */
  toggle(group: ProductOptionGroup, option: ProductOption): void {
    if (!this.available(option)) return;
    const selected = this.quantityOf(option) > 0;
    if (group.max_choices === 1) {
      if (selected && group.min_choices > 0) return;
      const groupIds = new Set(group.options.map((item) => item.id));
      this.setChoices([
        ...this.choices().filter((choice) => !groupIds.has(choice.optionId)),
        ...(selected ? [] : [{ optionId: option.id, quantity: 1, notes: '' }])
      ]);
      return;
    }
    if (selected) {
      this.remove(option);
    } else if (!this.isFull(group)) {
      this.choices.update((items) => [...items, { optionId: option.id, quantity: 1, notes: '' }]);
    }
  }

  increment(group: ProductOptionGroup, option: ProductOption): void {
    if (!this.available(option) || this.isFull(group)) return;
    if (this.quantityOf(option)) {
      this.choices.update((items) => items.map((choice) => (choice.optionId === option.id ? { ...choice, quantity: choice.quantity + 1 } : choice)));
    } else {
      this.choices.update((items) => [...items, { optionId: option.id, quantity: 1, notes: '' }]);
    }
  }

  decrement(option: ProductOption): void {
    const current = this.quantityOf(option);
    if (current <= 1) {
      this.remove(option);
      return;
    }
    this.choices.update((items) => items.map((choice) => (choice.optionId === option.id ? { ...choice, quantity: choice.quantity - 1 } : choice)));
  }

  toggleNote(option: ProductOption): void {
    this.openNotes.update((ids) => {
      const next = new Set(ids);
      if (next.has(option.id)) next.delete(option.id);
      else next.add(option.id);
      return next;
    });
  }

  setNote(option: ProductOption, value: string): void {
    this.choices.update((items) => items.map((choice) => (choice.optionId === option.id ? { ...choice, notes: value } : choice)));
  }

  confirm(): void {
    this.triedSubmit.set(true);
    if (this.problems().length) return;
    this.confirmed.emit({
      choices: this.choices().map((choice) => ({ ...choice, notes: choice.notes.trim() })),
      notes: this.notes().trim(),
      quantity: this.quantity()
    });
  }

  /** Desmarcar "Fazer combo" tira junto a batata e a bebida do combo. */
  private setChoices(choices: CartChoice[]): void {
    this.choices.set(pruneHiddenChoices(this.product(), choices));
  }

  private remove(option: ProductOption): void {
    this.setChoices(this.choices().filter((choice) => choice.optionId !== option.id));
    this.openNotes.update((ids) => {
      const next = new Set(ids);
      next.delete(option.id);
      return next;
    });
  }
}
