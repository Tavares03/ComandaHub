import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { LucideAngularModule } from 'lucide-angular';

import { ApiService } from '../../core/api.service';
import { AvailabilityResponse, Ingredient, IngredientUnit, Product, SalesChannel, StockMovement } from '../../core/models';
import { TenantService } from '../../core/tenant.service';
import { ToastService } from '../../core/toast.service';
import { CHANNELS, errorMessage, isPausedOn } from '../../shared/order-options';
import { AvailabilityDialogComponent, AvailabilityTarget } from './availability-dialog.component';

interface IngredientRow {
  ingredient: Ingredient;
  usedBy: Product[];
  /** Por canal: em quantos itens esta pausado */
  channels: Array<{ id: SalesChannel; short: string; paused: number }>;
  anyPaused: boolean;
  stock: 'untracked' | 'ok' | 'low' | 'out';
}

type DialogMode = 'purchase' | 'adjust' | 'edit' | 'history';

export const UNITS: Array<{ id: IngredientUnit; label: string }> = [
  { id: 'un', label: 'unidade (un)' },
  { id: 'kg', label: 'quilo (kg)' },
  { id: 'g', label: 'grama (g)' },
  { id: 'L', label: 'litro (L)' },
  { id: 'ml', label: 'mililitro (ml)' }
];

export function formatQty(value: number | string | null | undefined): string {
  return Number(value ?? 0).toLocaleString('pt-BR', { maximumFractionDigits: 3 });
}

/** Aba Ingredientes do Cardapio: cadastro, estoque (entrada, contagem, historico), custo e pausa. */
@Component({
  selector: 'app-ingredients-panel',
  standalone: true,
  imports: [CommonModule, FormsModule, LucideAngularModule, AvailabilityDialogComponent],
  template: `
    <div class="app-card overflow-hidden">
      <form class="grid gap-2 border-b border-zinc-100 p-4 sm:grid-cols-[1fr_150px_130px_auto]" (ngSubmit)="create()">
        <input class="focus-ring h-10 rounded-lg border border-zinc-200 px-3 text-sm" name="newName" placeholder="Novo ingrediente (ex.: Alface)"
               [ngModel]="draft().name" (ngModelChange)="patchDraft({ name: $event })" />
        <select class="focus-ring h-10 rounded-lg border border-zinc-200 bg-white px-2 text-sm" name="newUnit" aria-label="Unidade"
                [ngModel]="draft().unit" (ngModelChange)="patchDraft({ unit: $event })">
          @for (unit of units; track unit.id) { <option [ngValue]="unit.id">{{ unit.label }}</option> }
        </select>
        <input class="focus-ring h-10 rounded-lg border border-zinc-200 px-3 text-sm" name="newCost" type="number" step="0.01" min="0"
               placeholder="Custo por unidade" aria-label="Custo por unidade" [ngModel]="draft().cost" (ngModelChange)="patchDraft({ cost: $event })" />
        <button class="focus-ring inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-brand-500 px-4 text-sm font-bold text-white hover:bg-brand-600 disabled:opacity-50"
                type="submit" [disabled]="draft().name.trim().length < 2">
          <i-lucide name="plus" [size]="16" /> Adicionar
        </button>
      </form>

      @if (alerts().length) {
        <p class="flex items-center gap-2 border-b border-amber-100 bg-amber-50 px-4 py-2 text-sm font-semibold text-amber-900">
          <i-lucide name="triangle-alert" [size]="16" /> Repor: {{ alerts().join(', ') }}
        </p>
      }

      <ul class="divide-y divide-zinc-100">
        @for (row of rows(); track row.ingredient.id) {
          <li class="flex flex-wrap items-center gap-3 p-4">
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2">
                <p class="font-extrabold text-zinc-950">{{ row.ingredient.name }}</p>
                @switch (row.stock) {
                  @case ('untracked') { <span class="rounded-full bg-zinc-100 px-2 py-0.5 text-xs font-bold text-zinc-500">Sem controle de estoque</span> }
                  @case ('out') { <span class="rounded-full bg-red-600 px-2 py-0.5 text-xs font-bold text-white">Zerado: {{ qty(row.ingredient.stock_quantity) }} {{ row.ingredient.unit }}</span> }
                  @case ('low') { <span class="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-bold text-amber-800">Baixo: {{ qty(row.ingredient.stock_quantity) }} {{ row.ingredient.unit }}</span> }
                  @default { <span class="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-bold text-emerald-700">{{ qty(row.ingredient.stock_quantity) }} {{ row.ingredient.unit }}</span> }
                }
                @if (row.ingredient.auto_paused) {
                  <span class="rounded-full bg-red-50 px-2 py-0.5 text-xs font-bold text-red-700" title="Volta sozinho quando entrar mercadoria">Pausado automaticamente</span>
                }
              </div>
              <p class="mt-0.5 text-xs text-zinc-500">
                {{ cost(row.ingredient) | currency:'BRL':'symbol':'1.2-4' }} por {{ row.ingredient.unit }}
                @if (row.usedBy.length) { - em {{ row.usedBy.length }} item(ns): {{ usedByNames(row) }} } @else { - nenhum item usa ainda }
              </p>
              <div class="mt-1.5 flex flex-wrap gap-1.5">
                @for (channel of row.channels; track channel.id) {
                  <span class="rounded-full px-2 py-0.5 text-xs font-bold" [ngClass]="channel.paused ? 'bg-red-50 text-red-700' : 'bg-emerald-50 text-emerald-700'">
                    {{ channel.short }}{{ channel.paused ? ': em falta em ' + channel.paused + '/' + row.usedBy.length : '' }}
                  </span>
                }
              </div>
            </div>
            <div class="flex flex-wrap gap-1.5">
              <button class="focus-ring inline-flex h-9 items-center gap-1.5 rounded-lg border border-zinc-200 px-3 text-sm font-bold hover:bg-zinc-50" (click)="open('purchase', row.ingredient)">
                <i-lucide name="package-check" [size]="15" /> Entrada
              </button>
              <button class="focus-ring inline-flex h-9 items-center gap-1.5 rounded-lg border border-zinc-200 px-3 text-sm font-bold hover:bg-zinc-50" (click)="open('adjust', row.ingredient)">
                <i-lucide name="clipboard-list" [size]="15" /> Contagem
              </button>
              <button class="focus-ring inline-flex h-9 items-center gap-1.5 rounded-lg border border-red-200 px-3 text-sm font-bold text-red-700 hover:bg-red-50" (click)="openAvailability(row, 'pause')">
                <i-lucide name="circle-pause" [size]="15" /> Acabou
              </button>
              @if (row.anyPaused) {
                <button class="focus-ring inline-flex h-9 items-center gap-1.5 rounded-lg border border-emerald-200 px-3 text-sm font-bold text-emerald-700 hover:bg-emerald-50" (click)="openAvailability(row, 'resume')">
                  <i-lucide name="circle-play" [size]="15" /> Chegou
                </button>
              }
              <button class="focus-ring rounded-lg border border-zinc-200 p-2 text-zinc-600 hover:bg-zinc-50" (click)="open('history', row.ingredient)" [attr.aria-label]="'Historico de ' + row.ingredient.name" title="Historico do estoque">
                <i-lucide name="clock-3" [size]="15" />
              </button>
              <button class="focus-ring rounded-lg border border-zinc-200 p-2 text-zinc-600 hover:bg-zinc-50" (click)="open('edit', row.ingredient)" [attr.aria-label]="'Editar ' + row.ingredient.name" title="Editar">
                <i-lucide name="edit-3" [size]="15" />
              </button>
              <button class="focus-ring rounded-lg border border-red-200 p-2 text-red-600 hover:bg-red-50" (click)="remove(row)" [attr.aria-label]="'Excluir ' + row.ingredient.name" title="Excluir">
                <i-lucide name="trash-2" [size]="15" />
              </button>
            </div>
          </li>
        } @empty {
          <li class="p-8 text-center text-sm text-zinc-500">Nenhum ingrediente cadastrado.</li>
        }
      </ul>
    </div>

    @if (dialog(); as current) {
      <div class="fixed inset-0 z-50 bg-zinc-950/40" (click)="dialog.set(null)"></div>
      <section class="fixed inset-x-0 bottom-0 z-50 max-h-[90vh] overflow-y-auto rounded-t-2xl bg-white p-5 shadow-2xl sm:inset-auto sm:left-1/2 sm:top-1/2 sm:w-[460px] sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-2xl"
               role="dialog" aria-modal="true" [attr.aria-label]="dialogTitle(current.mode) + ' ' + current.ingredient.name">
        <div class="flex items-start justify-between gap-3">
          <div>
            <p class="text-xs font-bold uppercase text-brand-600">{{ dialogTitle(current.mode) }}</p>
            <h2 class="text-xl font-extrabold text-zinc-950">{{ current.ingredient.name }}</h2>
            @if (current.ingredient.stock_quantity !== null) {
              <p class="text-sm text-zinc-500">Estoque atual: {{ qty(current.ingredient.stock_quantity) }} {{ current.ingredient.unit }}</p>
            }
          </div>
          <button type="button" class="focus-ring rounded-md border border-zinc-200 p-2" (click)="dialog.set(null)" aria-label="Fechar">
            <i-lucide name="x" [size]="18" />
          </button>
        </div>

        @switch (current.mode) {
          @case ('history') {
            <ul class="mt-4 divide-y divide-zinc-100 text-sm">
              @for (movement of movements(); track movement.id) {
                <li class="flex items-center justify-between gap-3 py-2">
                  <div>
                    <p class="font-bold text-zinc-900">{{ reasonLabel(movement.reason) }}</p>
                    <p class="text-xs text-zinc-500">{{ movement.created_at | date:'dd/MM HH:mm' }}{{ movement.note ? ' - ' + movement.note : '' }}</p>
                  </div>
                  <div class="text-right">
                    <p class="font-extrabold" [ngClass]="Number(movement.delta) < 0 ? 'text-red-600' : 'text-emerald-700'">
                      {{ Number(movement.delta) > 0 ? '+' : '' }}{{ qty(movement.delta) }} {{ current.ingredient.unit }}
                    </p>
                    <p class="text-xs text-zinc-500">saldo {{ qty(movement.balance) }}</p>
                  </div>
                </li>
              } @empty {
                <li class="py-6 text-center text-zinc-500">Nenhuma movimentacao ainda.</li>
              }
            </ul>
          }
          @case ('edit') {
            <div class="mt-4 space-y-3">
              <label class="block">
                <span class="mb-1 block text-xs font-bold text-zinc-500">Nome</span>
                <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" [(ngModel)]="form.name" />
              </label>
              <div class="grid grid-cols-2 gap-2">
                <label class="block">
                  <span class="mb-1 block text-xs font-bold text-zinc-500">Unidade</span>
                  <select class="focus-ring h-10 w-full rounded-lg border border-zinc-200 bg-white px-2 text-sm" [(ngModel)]="form.unit">
                    @for (unit of units; track unit.id) { <option [ngValue]="unit.id">{{ unit.label }}</option> }
                  </select>
                </label>
                <label class="block">
                  <span class="mb-1 block text-xs font-bold text-zinc-500">Custo por {{ form.unit }}</span>
                  <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" type="number" step="0.01" min="0" [(ngModel)]="form.cost" />
                </label>
              </div>
              <label class="block">
                <span class="mb-1 block text-xs font-bold text-zinc-500">Avisar quando ficar abaixo de ({{ form.unit }})</span>
                <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" type="number" step="0.001" min="0" placeholder="Sem aviso"
                       [(ngModel)]="form.min" />
              </label>
              @if (current.ingredient.stock_quantity !== null) {
                <label class="flex items-start gap-2 text-sm font-bold text-zinc-700">
                  <input type="checkbox" class="mt-1" [(ngModel)]="form.track" />
                  <span>Controlar estoque<span class="block text-xs font-normal text-zinc-500">Desmarcado: para de dar baixa e de pausar sozinho.</span></span>
                </label>
              } @else {
                <p class="rounded-lg bg-zinc-50 p-3 text-xs text-zinc-600">Para comecar a controlar o estoque, faca uma <b>Contagem</b> ou uma <b>Entrada</b>.</p>
              }
            </div>
          }
          @default {
            <div class="mt-4 space-y-3">
              <label class="block">
                <span class="mb-1 block text-xs font-bold text-zinc-500">
                  {{ current.mode === 'purchase' ? 'Quanto chegou' : 'Quanto tem agora (contado)' }} ({{ current.ingredient.unit }})
                </span>
                <input class="focus-ring h-11 w-full rounded-lg border border-zinc-200 px-3 text-base font-bold" type="number" step="0.001" min="0" [(ngModel)]="form.quantity" />
              </label>
              @if (current.mode === 'purchase') {
                <label class="block">
                  <span class="mb-1 block text-xs font-bold text-zinc-500">Custo por {{ current.ingredient.unit }} nesta compra (opcional)</span>
                  <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" type="number" step="0.01" min="0" [(ngModel)]="form.cost" />
                </label>
              }
              <label class="block">
                <span class="mb-1 block text-xs font-bold text-zinc-500">Observacao</span>
                <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" maxlength="200"
                       [placeholder]="current.mode === 'purchase' ? 'Ex.: fornecedor, nota' : 'Ex.: contagem de fechamento'" [(ngModel)]="form.note" />
              </label>
              @if (current.ingredient.auto_paused && current.mode === 'purchase') {
                <p class="rounded-lg bg-emerald-50 p-3 text-xs font-semibold text-emerald-800">Ao dar entrada, os itens pausados automaticamente voltam a vender.</p>
              }
            </div>
          }
        }

        @if (current.mode !== 'history') {
          <div class="mt-5 flex gap-2">
            <button type="button" class="focus-ring h-11 rounded-lg border border-zinc-200 px-4 text-sm font-bold" (click)="dialog.set(null)">Cancelar</button>
            <button type="button" class="focus-ring inline-flex h-11 flex-1 items-center justify-center gap-2 rounded-lg bg-brand-500 text-sm font-extrabold text-white hover:bg-brand-600 disabled:opacity-50"
                    [disabled]="saving()" (click)="save(current.mode, current.ingredient)">
              <i-lucide name="save" [size]="16" /> Salvar
            </button>
          </div>
        }
      </section>
    }

    @if (availability(); as state) {
      <app-availability-dialog
        [target]="state.target"
        [action]="state.action"
        [pausedChannels]="state.paused"
        [usedBy]="state.usedBy"
        [multiStore]="multiStore()"
        (done)="availabilityDone(state, $event)"
        (closed)="availability.set(null)"
      />
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class IngredientsPanelComponent {
  private readonly api = inject(ApiService);
  private readonly tenant = inject(TenantService);
  private readonly toast = inject(ToastService);

  readonly ingredients = input<Ingredient[]>([]);
  readonly products = input<Product[]>([]);
  readonly multiStore = input(false);
  /** Algo mudou: o Cardapio recarrega itens e ingredientes */
  readonly changed = output<void>();

  readonly units = UNITS;
  readonly Number = Number;
  readonly draft = signal<{ name: string; unit: IngredientUnit; cost: number | null }>({ name: '', unit: 'un', cost: null });
  readonly dialog = signal<{ mode: DialogMode; ingredient: Ingredient } | null>(null);
  readonly movements = signal<StockMovement[]>([]);
  readonly saving = signal(false);
  readonly availability = signal<{ target: AvailabilityTarget; action: 'pause' | 'resume'; paused: SalesChannel[]; usedBy: Product[] } | null>(null);
  form = { name: '', unit: 'un' as IngredientUnit, cost: null as number | null, min: null as number | null, track: true, quantity: null as number | null, note: '' };

  readonly rows = computed<IngredientRow[]>(() =>
    this.ingredients().map((ingredient) => {
      const usedBy = this.products().filter((product) => product.ingredients.some((item) => item.ingredient_id === ingredient.id));
      const channels = CHANNELS.map((channel) => ({
        id: channel.id,
        short: channel.short,
        paused: usedBy.filter((product) =>
          product.ingredients.some((item) => item.ingredient_id === ingredient.id && isPausedOn(item.paused_channels, channel.id))
        ).length
      }));
      return { ingredient, usedBy, channels, anyPaused: channels.some((channel) => channel.paused > 0), stock: this.stockState(ingredient) };
    })
  );

  /** Ingredientes zerados ou abaixo do minimo */
  readonly alerts = computed(() => this.rows().filter((row) => row.stock === 'out' || row.stock === 'low').map((row) => row.ingredient.name));

  qty(value: number | string | null | undefined): string {
    return formatQty(value);
  }

  cost(ingredient: Ingredient): number {
    return Number(ingredient.cost_per_unit);
  }

  usedByNames(row: IngredientRow): string {
    return row.usedBy.map((product) => product.name).join(', ');
  }

  dialogTitle(mode: DialogMode): string {
    return { purchase: 'Entrada de mercadoria', adjust: 'Contagem do estoque', edit: 'Editar ingrediente', history: 'Historico do estoque' }[mode];
  }

  reasonLabel(reason: StockMovement['reason']): string {
    return { ORDER: 'Pedido', CANCEL: 'Pedido cancelado (devolvido)', PURCHASE: 'Entrada', ADJUST: 'Contagem' }[reason];
  }

  patchDraft(patch: Partial<{ name: string; unit: IngredientUnit; cost: number | null }>): void {
    this.draft.update((current) => ({ ...current, ...patch }));
  }

  create(): void {
    const establishment = this.tenant.current();
    const draft = this.draft();
    if (!establishment || draft.name.trim().length < 2) return;
    this.api.createIngredient(establishment.id, { name: draft.name.trim(), unit: draft.unit, cost_per_unit: Number(draft.cost) || 0 }).subscribe({
      next: () => {
        this.draft.set({ name: '', unit: draft.unit, cost: null });
        this.changed.emit();
      },
      error: (err) => this.toast.show('Erro', errorMessage(err, 'Nao foi possivel criar o ingrediente.'), 'error')
    });
  }

  open(mode: DialogMode, ingredient: Ingredient): void {
    this.form = {
      name: ingredient.name,
      unit: ingredient.unit,
      cost: mode === 'purchase' ? null : Number(ingredient.cost_per_unit),
      min: ingredient.min_stock === null ? null : Number(ingredient.min_stock),
      track: ingredient.stock_quantity !== null,
      quantity: mode === 'adjust' && ingredient.stock_quantity !== null ? Number(ingredient.stock_quantity) : null,
      note: ''
    };
    this.dialog.set({ mode, ingredient });
    if (mode === 'history') {
      const establishment = this.tenant.current();
      this.movements.set([]);
      if (establishment) this.api.stockMovements(establishment.id, ingredient.id).subscribe({ next: (items) => this.movements.set(items) });
    }
  }

  save(mode: DialogMode, ingredient: Ingredient): void {
    const establishment = this.tenant.current();
    if (!establishment) return;
    const request =
      mode === 'edit'
        ? this.api.updateIngredient(establishment.id, ingredient.id, {
            name: this.form.name.trim(),
            unit: this.form.unit,
            cost_per_unit: Number(this.form.cost) || 0,
            min_stock: this.form.min === null || (this.form.min as unknown) === '' ? null : Number(this.form.min),
            ...(ingredient.stock_quantity !== null && !this.form.track ? { track_stock: false } : {})
          })
        : this.api.stockEntry(establishment.id, ingredient.id, {
            kind: mode === 'purchase' ? 'PURCHASE' : 'ADJUST',
            quantity: Number(this.form.quantity) || 0,
            unit_cost: mode === 'purchase' && this.form.cost !== null && (this.form.cost as unknown) !== '' ? Number(this.form.cost) : null,
            note: this.form.note.trim() || null
          });
    if (mode !== 'edit' && (this.form.quantity === null || Number(this.form.quantity) < 0)) {
      this.toast.show('Informe a quantidade', 'Digite quanto chegou ou quanto tem.', 'error');
      return;
    }
    this.saving.set(true);
    request.subscribe({
      next: (updated) => {
        this.saving.set(false);
        this.dialog.set(null);
        if (mode !== 'edit') {
          this.toast.show('Estoque atualizado', `${updated.name}: ${formatQty(updated.stock_quantity)} ${updated.unit}`, 'success');
        }
        this.changed.emit();
      },
      error: (err) => {
        this.saving.set(false);
        this.toast.show('Erro', errorMessage(err, 'Nao foi possivel salvar.'), 'error');
      }
    });
  }

  remove(row: IngredientRow): void {
    const establishment = this.tenant.current();
    const warning = row.usedBy.length ? ` Ele sai de ${row.usedBy.length} item(ns).` : '';
    if (!establishment || !window.confirm(`Excluir o ingrediente ${row.ingredient.name}?${warning}`)) return;
    this.api.deleteIngredient(establishment.id, row.ingredient.id).subscribe({
      next: () => this.changed.emit(),
      error: (err) => this.toast.show('Erro', errorMessage(err, 'Nao foi possivel excluir.'), 'error')
    });
  }

  openAvailability(row: IngredientRow, action: 'pause' | 'resume'): void {
    this.availability.set({
      target: { type: 'ingredient', id: row.ingredient.id, name: row.ingredient.name },
      action,
      paused: row.channels.filter((channel) => channel.paused > 0).map((channel) => channel.id),
      usedBy: row.usedBy
    });
  }

  availabilityDone(state: { target: AvailabilityTarget; action: 'pause' | 'resume' }, result: AvailabilityResponse): void {
    const changed = result.results.reduce((sum, store) => sum + store.changes.length, 0);
    const stores = result.results.length > 1 ? ` em ${result.results.length} lojas` : '';
    this.toast.show(`${state.action === 'pause' ? 'Pausado' : 'Reativado'}: ${state.target.name}`, `${changed} lugar(es) atualizado(s)${stores}.`, 'success');
    this.availability.set(null);
    this.changed.emit();
  }

  private stockState(ingredient: Ingredient): IngredientRow['stock'] {
    if (ingredient.stock_quantity === null) return 'untracked';
    const stock = Number(ingredient.stock_quantity);
    if (stock <= 0) return 'out';
    if (ingredient.min_stock !== null && stock <= Number(ingredient.min_stock)) return 'low';
    return 'ok';
  }
}
