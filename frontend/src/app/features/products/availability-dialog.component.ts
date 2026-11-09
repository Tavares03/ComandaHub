import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, HostListener, OnInit, computed, effect, inject, input, output, signal, untracked } from '@angular/core';
import { LucideAngularModule } from 'lucide-angular';
import { Subscription } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { AvailabilityRequest, AvailabilityResponse, AvailabilityScope, Product, SalesChannel } from '../../core/models';
import { TenantService } from '../../core/tenant.service';
import { ToastService } from '../../core/toast.service';
import { CHANNELS, errorMessage } from '../../shared/order-options';

export interface AvailabilityTarget {
  type: 'product' | 'ingredient';
  id: string;
  name: string;
}

/**
 * Pergunta onde pausar/reativar: em quais canais, so no item ou em todo lugar que usa ele
 * (combos), e em quais lojas. Mostra antes o que vai mudar.
 */
@Component({
  selector: 'app-availability-dialog',
  standalone: true,
  imports: [CommonModule, LucideAngularModule],
  template: `
    <div class="fixed inset-0 z-50 bg-zinc-950/40" (click)="closed.emit()"></div>
    <section
      class="fixed inset-x-0 bottom-0 z-50 flex max-h-[92vh] flex-col overflow-hidden rounded-t-2xl bg-white shadow-2xl sm:inset-auto sm:left-1/2 sm:top-1/2 sm:w-[560px] sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-2xl"
      role="dialog"
      aria-modal="true"
      [attr.aria-label]="title()"
    >
      <header class="flex items-start justify-between gap-3 border-b border-zinc-100 p-5">
        <div>
          <p class="text-xs font-bold uppercase" [ngClass]="pausing() ? 'text-red-600' : 'text-emerald-700'">
            {{ pausing() ? 'Pausar' : 'Reativar' }} {{ target().type === 'ingredient' ? 'ingrediente' : 'item' }}
          </p>
          <h2 class="text-xl font-extrabold text-zinc-950">{{ target().name }}</h2>
        </div>
        <button type="button" class="focus-ring rounded-md border border-zinc-200 p-2" (click)="closed.emit()" aria-label="Fechar">
          <i-lucide name="x" [size]="18" />
        </button>
      </header>

      <div class="flex-1 space-y-5 overflow-y-auto p-5">
        <fieldset>
          <legend class="text-sm font-extrabold text-zinc-950">Em quais canais?</legend>
          <div class="mt-2 flex flex-wrap gap-2">
            @for (channel of channelList; track channel.id) {
              <button type="button" class="focus-ring inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-bold"
                      [attr.aria-pressed]="channels().has(channel.id)"
                      [ngClass]="channels().has(channel.id) ? 'border-brand-500 bg-brand-50 text-brand-800' : 'border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50'"
                      (click)="toggleChannel(channel.id)">
                <span class="flex h-4 w-4 items-center justify-center rounded border-2"
                      [ngClass]="channels().has(channel.id) ? 'border-brand-500 bg-brand-500 text-white' : 'border-zinc-300'">
                  @if (channels().has(channel.id)) { <i-lucide name="check" [size]="11" /> }
                </span>
                {{ channel.short }}
              </button>
            }
            <button type="button" class="focus-ring rounded-lg px-3 py-2 text-sm font-bold text-brand-700 hover:bg-brand-50" (click)="allChannels()">
              Todos
            </button>
          </div>
          <p class="mt-1 text-xs text-zinc-500">Local = balcao, retirada e delivery proprio.</p>
        </fieldset>

        <fieldset>
          <legend class="text-sm font-extrabold text-zinc-950">Onde?</legend>
          <div class="mt-2 space-y-2">
            @if (target().type === 'product') {
              <label class="flex cursor-pointer items-start gap-3 rounded-lg border p-3" [ngClass]="scope() === 'item' ? 'border-brand-500 bg-brand-50/60' : 'border-zinc-200'">
                <input type="radio" name="scope" class="mt-1" [checked]="scope() === 'item'" (change)="scope.set('item')" />
                <span>
                  <span class="block text-sm font-bold text-zinc-900">So este item</span>
                  <span class="block text-xs text-zinc-500">Dentro dos combos fica como esta.</span>
                </span>
              </label>
              <label class="flex cursor-pointer items-start gap-3 rounded-lg border p-3" [ngClass]="scope() === 'everywhere' ? 'border-brand-500 bg-brand-50/60' : 'border-zinc-200'">
                <input type="radio" name="scope" class="mt-1" [checked]="scope() === 'everywhere'" (change)="scope.set('everywhere')" />
                <span>
                  <span class="block text-sm font-bold text-zinc-900">Este item e todos os combos que usam ele</span>
                  <span class="block text-xs text-zinc-500">{{ pausing() ? 'Tambem sai' : 'Tambem volta' }} nas opcoes ligadas a ele em outros itens.</span>
                </span>
              </label>
            } @else {
              <label class="flex cursor-pointer items-start gap-3 rounded-lg border p-3" [ngClass]="scope() === 'everywhere' ? 'border-brand-500 bg-brand-50/60' : 'border-zinc-200'">
                <input type="radio" name="scope" class="mt-1" [checked]="scope() === 'everywhere'" (change)="scope.set('everywhere')" />
                <span>
                  <span class="block text-sm font-bold text-zinc-900">Todos os itens que usam {{ target().name }} ({{ usedBy().length }})</span>
                  <span class="block text-xs text-zinc-500">
                    {{ pausing() ? 'Item em que ele e principal sai do cardapio; nos outros, vende sem ele.' : 'Os itens voltam a sair com ele.' }}
                  </span>
                </span>
              </label>
              <label class="flex cursor-pointer items-start gap-3 rounded-lg border p-3" [ngClass]="scope() === 'selected' ? 'border-brand-500 bg-brand-50/60' : 'border-zinc-200'">
                <input type="radio" name="scope" class="mt-1" [checked]="scope() === 'selected'" (change)="scope.set('selected')" />
                <span class="block text-sm font-bold text-zinc-900">So em alguns itens</span>
              </label>
              @if (scope() === 'selected') {
                <div class="ml-7 space-y-1">
                  @for (product of usedBy(); track product.id) {
                    <label class="flex items-center gap-2 text-sm text-zinc-800">
                      <input type="checkbox" [checked]="selected().has(product.id)" (change)="toggleProduct(product.id)" />
                      {{ product.name }}
                    </label>
                  } @empty {
                    <p class="text-xs text-zinc-500">Nenhum item usa este ingrediente ainda.</p>
                  }
                </div>
              }
            }
          </div>
        </fieldset>

        @if (multiStore()) {
          <fieldset>
            <legend class="text-sm font-extrabold text-zinc-950">Em quais lojas?</legend>
            <div class="mt-2 grid gap-2 sm:grid-cols-2">
              <label class="flex cursor-pointer items-center gap-3 rounded-lg border p-3 text-sm font-bold" [ngClass]="!allStores() ? 'border-brand-500 bg-brand-50/60' : 'border-zinc-200'">
                <input type="radio" name="stores" [checked]="!allStores()" (change)="allStores.set(false)" /> So nesta loja
              </label>
              <label class="flex cursor-pointer items-center gap-3 rounded-lg border p-3 text-sm font-bold" [ngClass]="allStores() ? 'border-brand-500 bg-brand-50/60' : 'border-zinc-200'">
                <input type="radio" name="stores" [checked]="allStores()" (change)="allStores.set(true)" /> Em todas as minhas lojas
              </label>
            </div>
            <p class="mt-1 text-xs text-zinc-500">Nas outras lojas vale o {{ target().type === 'ingredient' ? 'ingrediente' : 'item' }} com o mesmo nome.</p>
          </fieldset>
        }

        <div class="rounded-xl bg-zinc-50 p-4">
          <p class="text-sm font-extrabold text-zinc-950">O que vai mudar</p>
          @if (!channels().size) {
            <p class="mt-1 text-sm text-zinc-500">Escolha pelo menos um canal.</p>
          } @else if (!preview()) {
            <p class="mt-1 text-sm text-zinc-500">{{ previewLoading() ? 'Calculando...' : 'Nada para mostrar.' }}</p>
          }
          @if (channels().size && preview(); as result) {
            @for (store of result.results; track store.establishment_id) {
              @if (result.results.length > 1) {
                <p class="mt-3 text-xs font-extrabold uppercase text-zinc-500">{{ store.establishment_name }}</p>
              }
              <ul class="mt-1 space-y-1">
                @for (change of store.changes; track $index) {
                  <li class="text-sm text-zinc-700"><span class="font-bold text-zinc-900">{{ change.product_name }}</span> - {{ change.what }}</li>
                } @empty {
                  <li class="text-sm text-zinc-500">Nada usa isso nesta loja.</li>
                }
              </ul>
            }
            @if (result.not_found_in.length) {
              <p class="mt-3 text-xs text-zinc-500">Nao existe em: {{ result.not_found_in.join(', ') }}</p>
            }
          }
        </div>
      </div>

      <footer class="flex gap-2 border-t border-zinc-100 p-4">
        <button type="button" class="focus-ring h-11 rounded-lg border border-zinc-200 px-4 text-sm font-bold" (click)="closed.emit()">Cancelar</button>
        <button type="button"
                class="focus-ring inline-flex h-11 flex-1 items-center justify-center gap-2 rounded-lg text-sm font-extrabold text-white disabled:opacity-50"
                [ngClass]="pausing() ? 'bg-red-600 hover:bg-red-700' : 'bg-emerald-600 hover:bg-emerald-700'"
                [disabled]="!canConfirm() || saving()" (click)="confirm()">
          <i-lucide [name]="pausing() ? 'circle-pause' : 'circle-play'" [size]="16" /> {{ confirmLabel() }}
        </button>
      </footer>
    </section>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class AvailabilityDialogComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly tenant = inject(TenantService);
  private readonly toast = inject(ToastService);

  readonly target = input.required<AvailabilityTarget>();
  readonly action = input<'pause' | 'resume'>('pause');
  /** Canais em que ja esta pausado: vem marcados ao reativar */
  readonly pausedChannels = input<SalesChannel[]>([]);
  /** Itens desta loja que usam o ingrediente */
  readonly usedBy = input<Product[]>([]);
  /** Usuario edita mais de uma loja: mostra "todas as minhas lojas" */
  readonly multiStore = input(false);
  readonly done = output<AvailabilityResponse>();
  readonly closed = output<void>();

  readonly channelList = CHANNELS;
  readonly channels = signal<Set<SalesChannel>>(new Set());
  readonly scope = signal<AvailabilityScope>('everywhere');
  readonly selected = signal<Set<string>>(new Set());
  readonly allStores = signal(false);
  readonly preview = signal<AvailabilityResponse | null>(null);
  readonly previewLoading = signal(false);
  readonly saving = signal(false);

  readonly pausing = computed(() => this.action() === 'pause');
  readonly title = computed(() => `${this.pausing() ? 'Pausar' : 'Reativar'} ${this.target().name}`);
  readonly canConfirm = computed(() => this.channels().size > 0 && (this.scope() !== 'selected' || this.selected().size > 0));
  readonly confirmLabel = computed(() => {
    const names = this.channelList.filter((channel) => this.channels().has(channel.id)).map((channel) => channel.short);
    const verb = this.pausing() ? 'Pausar' : 'Reativar';
    return names.length ? `${verb} no ${names.join(', ')}` : verb;
  });

  private previewTimer: ReturnType<typeof setTimeout> | null = null;
  private previewRequest: Subscription | null = null;

  constructor() {
    inject(DestroyRef).onDestroy(() => {
      if (this.previewTimer) clearTimeout(this.previewTimer);
      this.previewRequest?.unsubscribe();
    });
    // Recalcula a previa (dry_run) quando muda alguma escolha
    effect(() => {
      const request = this.request(true);
      untracked(() => this.schedulePreview(request));
    }, { allowSignalWrites: true });
  }

  ngOnInit(): void {
    if (!this.pausing()) this.channels.set(new Set(this.pausedChannels()));
    this.selected.set(new Set(this.usedBy().map((product) => product.id)));
  }

  @HostListener('document:keydown.escape')
  onEscape(): void {
    this.closed.emit();
  }

  toggleChannel(channel: SalesChannel): void {
    this.channels.update((current) => {
      const next = new Set(current);
      if (next.has(channel)) next.delete(channel);
      else next.add(channel);
      return next;
    });
  }

  allChannels(): void {
    this.channels.set(new Set(this.channelList.map((channel) => channel.id)));
  }

  toggleProduct(id: string): void {
    this.selected.update((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  confirm(): void {
    const establishment = this.tenant.current();
    if (!establishment || !this.canConfirm()) return;
    this.saving.set(true);
    this.api.changeAvailability(establishment.id, this.request(false)).subscribe({
      next: (result) => {
        this.saving.set(false);
        this.done.emit(result);
      },
      error: (err) => {
        this.saving.set(false);
        this.toast.show('Nao foi possivel salvar', errorMessage(err, 'Tente novamente.'), 'error');
      }
    });
  }

  private request(dryRun: boolean): AvailabilityRequest {
    return {
      target_type: this.target().type,
      target_id: this.target().id,
      action: this.action(),
      channels: this.channelList.map((channel) => channel.id).filter((id) => this.channels().has(id)),
      scope: this.scope(),
      product_ids: this.scope() === 'selected' ? [...this.selected()] : [],
      all_establishments: this.allStores(),
      dry_run: dryRun
    };
  }

  private schedulePreview(request: AvailabilityRequest): void {
    if (this.previewTimer) clearTimeout(this.previewTimer);
    this.previewRequest?.unsubscribe();
    const establishment = this.tenant.current();
    if (!establishment || !request.channels.length || (request.scope === 'selected' && !request.product_ids?.length)) {
      this.preview.set(null);
      return;
    }
    this.previewLoading.set(true);
    this.previewTimer = setTimeout(() => {
      this.previewRequest = this.api.changeAvailability(establishment.id, request).subscribe({
        next: (result) => {
          this.preview.set(result);
          this.previewLoading.set(false);
        },
        error: () => this.previewLoading.set(false)
      });
    }, 250);
  }
}
