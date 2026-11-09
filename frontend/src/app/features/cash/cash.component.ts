import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, effect, inject, signal, untracked } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { LucideAngularModule } from 'lucide-angular';

import { ApiService } from '../../core/api.service';
import { CashSummary, PaymentMethod } from '../../core/models';
import { TenantService } from '../../core/tenant.service';
import { ToastService } from '../../core/toast.service';
import { errorMessage } from '../../shared/order-options';
import { paymentMethodLabel } from '../../shared/status';

type CashDialog = { mode: 'WITHDRAWAL' | 'SUPPLY' | 'CLOSE' };

/** Caixa: abre com troco, mostra o turno por forma de pagamento, sangria/reforco e fecha com a contagem. */
@Component({
  selector: 'app-cash',
  standalone: true,
  imports: [CommonModule, FormsModule, LucideAngularModule],
  template: `
    <section class="space-y-5">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 class="text-2xl font-extrabold tracking-normal text-zinc-950">Caixa</h1>
          <p class="mt-1 text-sm text-zinc-500">Abertura, sangria, reforco e fechamento com a conferencia da gaveta.</p>
        </div>
        @if (current(); as cash) {
          <div class="flex flex-wrap gap-2">
            <button class="focus-ring inline-flex h-10 items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 text-sm font-bold hover:bg-zinc-50" (click)="openDialog('WITHDRAWAL')">
              <i-lucide name="minus" [size]="16" /> Sangria
            </button>
            <button class="focus-ring inline-flex h-10 items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 text-sm font-bold hover:bg-zinc-50" (click)="openDialog('SUPPLY')">
              <i-lucide name="plus" [size]="16" /> Reforco
            </button>
            <button class="focus-ring inline-flex h-10 items-center gap-2 rounded-lg bg-zinc-900 px-4 text-sm font-bold text-white hover:bg-zinc-800" (click)="openDialog('CLOSE')">
              <i-lucide name="lock" [size]="16" /> Fechar caixa
            </button>
          </div>
        }
      </div>

      @if (loaded() && !current()) {
        <div class="app-card flex flex-wrap items-end gap-4 p-5">
          <div class="flex-1">
            <p class="inline-flex items-center gap-2 rounded-full bg-zinc-100 px-3 py-1 text-xs font-bold text-zinc-600"><i-lucide name="lock" [size]="13" /> Caixa fechado</p>
            <h2 class="mt-2 text-lg font-extrabold text-zinc-950">Abrir o caixa</h2>
            <p class="text-sm text-zinc-500">Informe quanto tem de troco na gaveta agora.</p>
          </div>
          <label class="block w-full sm:w-48">
            <span class="mb-1 block text-xs font-bold text-zinc-500">Troco inicial (R$)</span>
            <input class="focus-ring h-11 w-full rounded-lg border border-zinc-200 px-3 text-base font-bold" type="number" step="0.01" min="0"
                   [ngModel]="openingAmount()" (ngModelChange)="openingAmount.set($event)" />
          </label>
          <button class="focus-ring inline-flex h-11 items-center gap-2 rounded-lg bg-brand-500 px-5 text-sm font-extrabold text-white hover:bg-brand-600 disabled:opacity-50"
                  [disabled]="saving()" (click)="open()">
            <i-lucide name="banknote" [size]="16" /> Abrir caixa
          </button>
        </div>
      }

      @if (current(); as cash) {
        <p class="inline-flex flex-wrap items-center gap-2 text-sm text-zinc-600">
          <span class="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700"><i-lucide name="check-circle-2" [size]="13" /> Caixa aberto</span>
          desde {{ cash.opened_at | date:'dd/MM HH:mm' }}{{ cash.opened_by_name ? ' por ' + cash.opened_by_name : '' }} - troco inicial {{ money(cash.opening_amount) | currency:'BRL':'symbol':'1.2-2' }}
        </p>

        <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <div class="app-card p-4">
            <p class="text-xs font-bold uppercase text-zinc-500">Vendas no turno</p>
            <p class="mt-1 text-2xl font-extrabold text-zinc-950">{{ money(cash.total_sales) | currency:'BRL':'symbol':'1.2-2' }}</p>
            <p class="text-xs text-zinc-500">{{ cash.order_count }} pedido(s){{ cash.canceled_count ? ' - ' + cash.canceled_count + ' cancelado(s)' : '' }}</p>
          </div>
          <div class="app-card p-4 ring-2 ring-brand-200">
            <p class="text-xs font-bold uppercase text-zinc-500">Dinheiro na gaveta (esperado)</p>
            <p class="mt-1 text-2xl font-extrabold text-zinc-950">{{ money(cash.expected_cash) | currency:'BRL':'symbol':'1.2-2' }}</p>
            <p class="text-xs text-zinc-500">troco + dinheiro + reforcos - sangrias</p>
          </div>
          <div class="app-card p-4">
            <p class="text-xs font-bold uppercase text-zinc-500">Sangrias</p>
            <p class="mt-1 text-2xl font-extrabold text-red-700">{{ money(cash.withdrawals) | currency:'BRL':'symbol':'1.2-2' }}</p>
          </div>
          <div class="app-card p-4">
            <p class="text-xs font-bold uppercase text-zinc-500">Reforcos</p>
            <p class="mt-1 text-2xl font-extrabold text-emerald-700">{{ money(cash.supplies) | currency:'BRL':'symbol':'1.2-2' }}</p>
          </div>
        </div>

        <div class="grid gap-4 xl:grid-cols-2">
          <div class="app-card p-5">
            <h2 class="text-base font-extrabold text-zinc-950">Por forma de pagamento</h2>
            <ul class="mt-3 divide-y divide-zinc-100">
              @for (row of cash.sales_by_method; track row.payment_method) {
                <li class="flex items-center justify-between py-2.5 text-sm">
                  <span class="font-bold text-zinc-800">{{ methodLabel(row.payment_method) }} <span class="font-normal text-zinc-500">- {{ row.orders }} pedido(s)</span></span>
                  <span class="font-extrabold">{{ money(row.total) | currency:'BRL':'symbol':'1.2-2' }}</span>
                </li>
              } @empty {
                <li class="py-6 text-center text-sm text-zinc-500">Nenhuma venda neste turno ainda.</li>
              }
            </ul>
          </div>
          <div class="app-card p-5">
            <h2 class="text-base font-extrabold text-zinc-950">Sangrias e reforcos</h2>
            <ul class="mt-3 divide-y divide-zinc-100">
              @for (movement of cash.movements; track movement.id) {
                <li class="flex items-center justify-between gap-3 py-2.5 text-sm">
                  <div>
                    <p class="font-bold text-zinc-800">{{ movement.kind === 'WITHDRAWAL' ? 'Sangria' : 'Reforco' }}{{ movement.note ? ' - ' + movement.note : '' }}</p>
                    <p class="text-xs text-zinc-500">{{ movement.created_at | date:'HH:mm' }}{{ movement.user_name ? ' - ' + movement.user_name : '' }}</p>
                  </div>
                  <span class="font-extrabold" [ngClass]="movement.kind === 'WITHDRAWAL' ? 'text-red-700' : 'text-emerald-700'">
                    {{ movement.kind === 'WITHDRAWAL' ? '-' : '+' }}{{ money(movement.amount) | currency:'BRL':'symbol':'1.2-2' }}
                  </span>
                </li>
              } @empty {
                <li class="py-6 text-center text-sm text-zinc-500">Nenhuma sangria ou reforco.</li>
              }
            </ul>
          </div>
        </div>
      }

      <div class="app-card p-5">
        <h2 class="text-base font-extrabold text-zinc-950">Fechamentos anteriores</h2>
        <div class="mt-3 overflow-x-auto">
          <table class="w-full min-w-[640px] text-left text-sm">
            <thead class="text-xs uppercase text-zinc-500">
              <tr><th class="py-2">Aberto</th><th>Fechado</th><th>Vendas</th><th>Esperado</th><th>Contado</th><th>Diferenca</th></tr>
            </thead>
            <tbody class="divide-y divide-zinc-100">
              @for (session of closedHistory(); track session.id) {
                <tr>
                  <td class="py-2.5">{{ session.opened_at | date:'dd/MM HH:mm' }}<span class="block text-xs text-zinc-500">{{ session.opened_by_name }}</span></td>
                  <td>{{ session.closed_at | date:'dd/MM HH:mm' }}<span class="block text-xs text-zinc-500">{{ session.closed_by_name }}</span></td>
                  <td class="font-bold">{{ money(session.total_sales) | currency:'BRL':'symbol':'1.2-2' }}</td>
                  <td>{{ money(session.expected_cash) | currency:'BRL':'symbol':'1.2-2' }}</td>
                  <td>{{ money(session.counted_amount) | currency:'BRL':'symbol':'1.2-2' }}</td>
                  <td class="font-extrabold" [ngClass]="differenceClass(session.difference)">{{ money(session.difference) | currency:'BRL':'symbol':'1.2-2' }}</td>
                </tr>
              } @empty {
                <tr><td colspan="6" class="py-6 text-center text-zinc-500">Nenhum caixa fechado ainda.</td></tr>
              }
            </tbody>
          </table>
        </div>
      </div>
    </section>

    @if (dialog(); as dlg) {
      <div class="fixed inset-0 z-50 bg-zinc-950/40" (click)="dialog.set(null)"></div>
      <section class="fixed inset-x-0 bottom-0 z-50 rounded-t-2xl bg-white p-5 shadow-2xl sm:inset-auto sm:left-1/2 sm:top-1/2 sm:w-[440px] sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-2xl"
               role="dialog" aria-modal="true" [attr.aria-label]="dialogTitle(dlg.mode)">
        <div class="flex items-start justify-between gap-3">
          <h2 class="text-xl font-extrabold text-zinc-950">{{ dialogTitle(dlg.mode) }}</h2>
          <button type="button" class="focus-ring rounded-md border border-zinc-200 p-2" (click)="dialog.set(null)" aria-label="Fechar">
            <i-lucide name="x" [size]="18" />
          </button>
        </div>
        <div class="mt-4 space-y-3">
          <label class="block">
            <span class="mb-1 block text-xs font-bold text-zinc-500">{{ dlg.mode === 'CLOSE' ? 'Quanto tem na gaveta (contado)' : 'Valor' }} (R$)</span>
            <input class="focus-ring h-11 w-full rounded-lg border border-zinc-200 px-3 text-base font-bold" type="number" step="0.01" min="0"
                   [ngModel]="amount()" (ngModelChange)="amount.set($event)" />
          </label>
          @if (dlg.mode === 'CLOSE' && current(); as cash) {
            <div class="space-y-1 rounded-lg bg-zinc-50 p-3 text-sm">
              <div class="flex justify-between"><span class="text-zinc-500">Esperado na gaveta</span><span class="font-bold">{{ money(cash.expected_cash) | currency:'BRL':'symbol':'1.2-2' }}</span></div>
              @if (amount() !== null && amount() !== '') {
                <div class="flex justify-between"><span class="text-zinc-500">Diferenca</span>
                  <span class="font-extrabold" [ngClass]="differenceClass(closingDifference())">{{ closingDifference() | currency:'BRL':'symbol':'1.2-2' }}</span>
                </div>
              }
            </div>
          }
          <label class="block">
            <span class="mb-1 block text-xs font-bold text-zinc-500">{{ dlg.mode === 'CLOSE' ? 'Observacao do fechamento' : 'Motivo' }}</span>
            <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" maxlength="200"
                   [placeholder]="dlg.mode === 'WITHDRAWAL' ? 'Ex.: deposito, pagamento de fornecedor' : dlg.mode === 'SUPPLY' ? 'Ex.: mais troco' : 'Opcional'"
                   [ngModel]="note()" (ngModelChange)="note.set($event)" />
          </label>
        </div>
        <div class="mt-5 flex gap-2">
          <button type="button" class="focus-ring h-11 rounded-lg border border-zinc-200 px-4 text-sm font-bold" (click)="dialog.set(null)">Cancelar</button>
          <button type="button" class="focus-ring inline-flex h-11 flex-1 items-center justify-center gap-2 rounded-lg bg-brand-500 text-sm font-extrabold text-white hover:bg-brand-600 disabled:opacity-50"
                  [disabled]="saving() || amount() === null || amount() === ''" (click)="confirm(dlg.mode)">
            <i-lucide name="save" [size]="16" /> {{ dlg.mode === 'CLOSE' ? 'Fechar caixa' : 'Registrar' }}
          </button>
        </div>
      </section>
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class CashComponent {
  private readonly api = inject(ApiService);
  private readonly tenant = inject(TenantService);
  private readonly toast = inject(ToastService);

  readonly current = signal<CashSummary | null>(null);
  readonly history = signal<CashSummary[]>([]);
  readonly loaded = signal(false);
  readonly saving = signal(false);
  readonly openingAmount = signal<number | string>(100);
  readonly dialog = signal<CashDialog | null>(null);
  readonly amount = signal<number | string | null>(null);
  readonly note = signal('');

  readonly closedHistory = computed(() => this.history().filter((session) => session.closed_at));
  readonly closingDifference = computed(() => Number(this.amount() || 0) - Number(this.current()?.expected_cash ?? 0));

  constructor() {
    effect(() => {
      const establishment = this.tenant.current();
      if (establishment) untracked(() => this.load(establishment.id));
    }, { allowSignalWrites: true });
  }

  load(establishmentId: string): void {
    this.api.currentCash(establishmentId).subscribe({
      next: (cash) => {
        this.current.set(cash);
        this.loaded.set(true);
      }
    });
    this.api.cashHistory(establishmentId).subscribe({ next: (items) => this.history.set(items) });
  }

  money(value: number | string | null | undefined): number {
    return Number(value ?? 0);
  }

  methodLabel(method: PaymentMethod): string {
    return paymentMethodLabel(method);
  }

  differenceClass(value: number | string | null | undefined): string {
    const diff = Number(value ?? 0);
    if (Math.abs(diff) < 0.005) return 'text-emerald-700';
    return diff < 0 ? 'text-red-700' : 'text-amber-700';
  }

  dialogTitle(mode: CashDialog['mode']): string {
    return { WITHDRAWAL: 'Sangria (tirar dinheiro)', SUPPLY: 'Reforco (colocar troco)', CLOSE: 'Fechar caixa' }[mode];
  }

  openDialog(mode: CashDialog['mode']): void {
    this.amount.set(null);
    this.note.set('');
    this.dialog.set({ mode });
  }

  open(): void {
    const establishment = this.tenant.current();
    if (!establishment) return;
    this.saving.set(true);
    this.api.openCash(establishment.id, Number(this.openingAmount()) || 0).subscribe({
      next: (cash) => {
        this.saving.set(false);
        this.current.set(cash);
        this.toast.show('Caixa aberto', 'Bom trabalho!', 'success');
      },
      error: (err) => {
        this.saving.set(false);
        this.toast.show('Erro', errorMessage(err, 'Nao foi possivel abrir o caixa.'), 'error');
      }
    });
  }

  confirm(mode: CashDialog['mode']): void {
    const establishment = this.tenant.current();
    if (!establishment) return;
    const amount = Number(this.amount()) || 0;
    const note = this.note().trim() || null;
    this.saving.set(true);
    const request =
      mode === 'CLOSE' ? this.api.closeCash(establishment.id, amount, note) : this.api.cashMovement(establishment.id, mode, amount, note);
    request.subscribe({
      next: (cash) => {
        this.saving.set(false);
        this.dialog.set(null);
        if (mode === 'CLOSE') {
          const diff = Number(cash.difference ?? 0);
          const text = Math.abs(diff) < 0.005 ? 'Bateu certinho.' : diff < 0 ? `Faltou ${(-diff).toFixed(2)}.` : `Sobrou ${diff.toFixed(2)}.`;
          this.toast.show('Caixa fechado', text, Math.abs(diff) < 0.005 ? 'success' : 'info');
          this.load(establishment.id);
        } else {
          this.current.set(cash);
        }
      },
      error: (err) => {
        this.saving.set(false);
        this.toast.show('Erro', errorMessage(err, 'Nao foi possivel salvar.'), 'error');
      }
    });
  }
}
