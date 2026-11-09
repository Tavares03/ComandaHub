import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, effect, inject, signal, untracked } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { LucideAngularModule } from 'lucide-angular';

import { ApiService } from '../../core/api.service';
import { Coupon, Customer, Establishment } from '../../core/models';
import { TenantService } from '../../core/tenant.service';
import { ToastService } from '../../core/toast.service';
import { errorMessage } from '../../shared/order-options';

interface CouponDraft {
  code: string;
  kind: 'PERCENT' | 'FIXED';
  value: number | null;
  min_order: number | null;
  max_uses: number | null;
  valid_until: string;
}

export function formatPhone(phone: string): string {
  const d = phone.replace(/\D/g, '');
  if (d.length === 11) return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`;
  if (d.length === 10) return `(${d.slice(0, 2)}) ${d.slice(2, 6)}-${d.slice(6)}`;
  return phone;
}

/** Clientes (cadastrados pelo telefone nos pedidos), fidelidade e cupons. */
@Component({
  selector: 'app-customers',
  standalone: true,
  imports: [CommonModule, FormsModule, LucideAngularModule],
  template: `
    <section class="space-y-5">
      <div>
        <h1 class="text-2xl font-extrabold tracking-normal text-zinc-950">Clientes</h1>
        <p class="mt-1 text-sm text-zinc-500">Quem ja pediu, quanto gastou, fidelidade e cupons de desconto.</p>
      </div>

      <div class="inline-flex rounded-lg border border-zinc-200 bg-white p-1" role="tablist">
        <button type="button" role="tab" class="focus-ring rounded-md px-4 py-1.5 text-sm font-bold" [attr.aria-selected]="tab() === 'customers'"
                [ngClass]="tab() === 'customers' ? 'bg-zinc-900 text-white' : 'text-zinc-600 hover:bg-zinc-50'" (click)="tab.set('customers')">Clientes</button>
        <button type="button" role="tab" class="focus-ring rounded-md px-4 py-1.5 text-sm font-bold" [attr.aria-selected]="tab() === 'coupons'"
                [ngClass]="tab() === 'coupons' ? 'bg-zinc-900 text-white' : 'text-zinc-600 hover:bg-zinc-50'" (click)="tab.set('coupons')">Cupons</button>
      </div>

      @if (tab() === 'customers') {
        <div class="app-card overflow-hidden">
          <div class="flex flex-wrap items-center gap-3 border-b border-zinc-100 p-4">
            <label class="relative block w-full sm:w-80">
              <i-lucide class="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" name="search" [size]="18" />
              <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 bg-white pl-10 pr-3 text-sm" placeholder="Buscar por nome ou telefone"
                     [ngModel]="search()" (ngModelChange)="onSearch($event)" />
            </label>
            @if (store(); as settings) {
              <p class="text-xs text-zinc-500">
                @if (settings.loyalty_enabled) {
                  Fidelidade ligada: a cada {{ settings.loyalty_goal }} pedidos, o proximo tem {{ money(settings.loyalty_reward) | currency:'BRL':'symbol':'1.2-2' }} de desconto.
                } @else {
                  Fidelidade desligada (ligue em Configuracoes).
                }
              </p>
            }
          </div>
          <div class="overflow-x-auto">
            <table class="w-full min-w-[720px] text-left text-sm">
              <thead class="bg-zinc-50 text-xs uppercase text-zinc-500">
                <tr><th class="px-4 py-2">Cliente</th><th>Telefone</th><th>Pedidos</th><th>Total gasto</th><th>Ultimo pedido</th><th>Fidelidade</th><th></th></tr>
              </thead>
              <tbody class="divide-y divide-zinc-100">
                @for (customer of customers(); track customer.id) {
                  <tr>
                    <td class="px-4 py-3">
                      <p class="font-bold text-zinc-900">{{ customer.name }}</p>
                      <p class="max-w-64 truncate text-xs text-zinc-500">{{ customer.address }}{{ customer.neighborhood ? ' - ' + customer.neighborhood : '' }}</p>
                    </td>
                    <td>
                      <a class="font-semibold text-brand-700 hover:underline" [href]="whatsapp(customer.phone)" target="_blank" rel="noopener">{{ phone(customer.phone) }}</a>
                    </td>
                    <td class="font-bold">{{ customer.order_count }}</td>
                    <td class="font-bold">{{ money(customer.total_spent) | currency:'BRL':'symbol':'1.2-2' }}</td>
                    <td>{{ customer.last_order_at ? (customer.last_order_at | date:'dd/MM/yy HH:mm') : '-' }}</td>
                    <td>
                      @if (customer.reward_available) {
                        <span class="rounded-full bg-emerald-50 px-2 py-1 text-xs font-bold text-emerald-700">Recompensa disponivel</span>
                      } @else if (store()?.loyalty_enabled) {
                        <span class="text-xs font-bold text-zinc-600">{{ customer.loyalty_points }}/{{ store()?.loyalty_goal }}</span>
                      }
                    </td>
                    <td class="pr-4 text-right">
                      <button class="focus-ring rounded-lg border border-zinc-200 p-2 text-zinc-600 hover:bg-zinc-50" (click)="edit(customer)" [attr.aria-label]="'Editar ' + customer.name">
                        <i-lucide name="edit-3" [size]="15" />
                      </button>
                    </td>
                  </tr>
                } @empty {
                  <tr><td colspan="7" class="p-8 text-center text-zinc-500">Nenhum cliente ainda. Eles aparecem aqui quando o pedido tem telefone.</td></tr>
                }
              </tbody>
            </table>
          </div>
        </div>
      } @else {
        <div class="grid gap-5 xl:grid-cols-[1fr_360px]">
          <div class="app-card overflow-hidden">
            <ul class="divide-y divide-zinc-100">
              @for (coupon of coupons(); track coupon.id) {
                <li class="flex flex-wrap items-center gap-3 p-4" [class.opacity-60]="!coupon.active">
                  <div class="min-w-0 flex-1">
                    <p class="font-mono text-base font-extrabold text-zinc-950">{{ coupon.code }}</p>
                    <p class="text-xs text-zinc-500">
                      {{ coupon.kind === 'PERCENT' ? money(coupon.value) + '% de desconto' : (money(coupon.value) | currency:'BRL':'symbol':'1.2-2') + ' de desconto' }}
                      @if (money(coupon.min_order) > 0) { - pedido minimo {{ money(coupon.min_order) | currency:'BRL':'symbol':'1.2-2' }} }
                      @if (coupon.valid_until) { - vale ate {{ coupon.valid_until | date:'dd/MM/yyyy' }} }
                    </p>
                    <p class="text-xs font-bold text-zinc-600">Usado {{ coupon.uses }}{{ coupon.max_uses ? ' de ' + coupon.max_uses : '' }} vez(es)</p>
                  </div>
                  <button class="focus-ring h-9 rounded-lg border px-3 text-sm font-bold"
                          [ngClass]="coupon.active ? 'border-zinc-200 text-zinc-700 hover:bg-zinc-50' : 'border-emerald-200 text-emerald-700 hover:bg-emerald-50'"
                          (click)="toggleCoupon(coupon)">{{ coupon.active ? 'Desativar' : 'Ativar' }}</button>
                  <button class="focus-ring rounded-lg border border-red-200 p-2 text-red-600 hover:bg-red-50" (click)="deleteCoupon(coupon)" [attr.aria-label]="'Excluir ' + coupon.code">
                    <i-lucide name="trash-2" [size]="15" />
                  </button>
                </li>
              } @empty {
                <li class="p-8 text-center text-sm text-zinc-500">Nenhum cupom criado.</li>
              }
            </ul>
          </div>
          <form class="app-card h-max space-y-3 p-5" (ngSubmit)="createCoupon()">
            <h2 class="text-lg font-extrabold text-zinc-950">Novo cupom</h2>
            <label class="block">
              <span class="mb-1 block text-xs font-bold text-zinc-500">Codigo</span>
              <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 font-mono text-sm uppercase" name="code" placeholder="EX.: SEXTOU15"
                     [(ngModel)]="draft.code" />
            </label>
            <div class="grid grid-cols-2 gap-2">
              <label class="block">
                <span class="mb-1 block text-xs font-bold text-zinc-500">Tipo</span>
                <select class="focus-ring h-10 w-full rounded-lg border border-zinc-200 bg-white px-2 text-sm" name="kind" [(ngModel)]="draft.kind">
                  <option value="PERCENT">% do pedido</option>
                  <option value="FIXED">Valor em R$</option>
                </select>
              </label>
              <label class="block">
                <span class="mb-1 block text-xs font-bold text-zinc-500">{{ draft.kind === 'PERCENT' ? 'Percentual' : 'Valor (R$)' }}</span>
                <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" type="number" step="0.01" min="0" name="value" [(ngModel)]="draft.value" />
              </label>
            </div>
            <div class="grid grid-cols-2 gap-2">
              <label class="block">
                <span class="mb-1 block text-xs font-bold text-zinc-500">Pedido minimo (R$)</span>
                <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" type="number" step="0.01" min="0" name="min" [(ngModel)]="draft.min_order" />
              </label>
              <label class="block">
                <span class="mb-1 block text-xs font-bold text-zinc-500">Limite de usos</span>
                <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" type="number" min="1" placeholder="Sem limite" name="max" [(ngModel)]="draft.max_uses" />
              </label>
            </div>
            <label class="block">
              <span class="mb-1 block text-xs font-bold text-zinc-500">Vale ate (opcional)</span>
              <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" type="date" name="until" [(ngModel)]="draft.valid_until" />
            </label>
            <button class="focus-ring inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-brand-500 text-sm font-extrabold text-white hover:bg-brand-600 disabled:opacity-50"
                    type="submit" [disabled]="draft.code.trim().length < 2 || !draft.value">
              <i-lucide name="plus" [size]="16" /> Criar cupom
            </button>
          </form>
        </div>
      }
    </section>

    @if (editing(); as customer) {
      <div class="fixed inset-0 z-50 bg-zinc-950/40" (click)="editing.set(null)"></div>
      <section class="fixed inset-x-0 bottom-0 z-50 rounded-t-2xl bg-white p-5 shadow-2xl sm:inset-auto sm:left-1/2 sm:top-1/2 sm:w-[460px] sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-2xl"
               role="dialog" aria-modal="true" aria-label="Editar cliente">
        <h2 class="text-xl font-extrabold text-zinc-950">{{ phone(customer.phone) }}</h2>
        <div class="mt-4 space-y-3">
          <label class="block"><span class="mb-1 block text-xs font-bold text-zinc-500">Nome</span>
            <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" [(ngModel)]="form.name" /></label>
          <label class="block"><span class="mb-1 block text-xs font-bold text-zinc-500">Endereco</span>
            <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" [(ngModel)]="form.address" /></label>
          <label class="block"><span class="mb-1 block text-xs font-bold text-zinc-500">Bairro</span>
            <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" [(ngModel)]="form.neighborhood" /></label>
          <label class="block"><span class="mb-1 block text-xs font-bold text-zinc-500">Observacoes (ex.: alergia, preferencia)</span>
            <textarea class="focus-ring min-h-20 w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm" [(ngModel)]="form.notes"></textarea></label>
        </div>
        <div class="mt-5 flex gap-2">
          <button type="button" class="focus-ring h-11 rounded-lg border border-zinc-200 px-4 text-sm font-bold" (click)="editing.set(null)">Cancelar</button>
          <button type="button" class="focus-ring inline-flex h-11 flex-1 items-center justify-center gap-2 rounded-lg bg-brand-500 text-sm font-extrabold text-white hover:bg-brand-600" (click)="saveCustomer(customer)">
            <i-lucide name="save" [size]="16" /> Salvar
          </button>
        </div>
      </section>
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class CustomersComponent {
  private readonly api = inject(ApiService);
  private readonly tenant = inject(TenantService);
  private readonly toast = inject(ToastService);
  private searchTimer: ReturnType<typeof setTimeout> | null = null;

  readonly tab = signal<'customers' | 'coupons'>('customers');
  readonly customers = signal<Customer[]>([]);
  readonly coupons = signal<Coupon[]>([]);
  readonly store = signal<Establishment | null>(null);
  readonly search = signal('');
  readonly editing = signal<Customer | null>(null);
  form = { name: '', address: '', neighborhood: '', notes: '' };
  draft: CouponDraft = this.emptyDraft();

  constructor() {
    effect(() => {
      const establishment = this.tenant.current();
      if (establishment) untracked(() => this.load(establishment.id));
    }, { allowSignalWrites: true });
  }

  load(establishmentId: string): void {
    this.api.customers(establishmentId, this.search()).subscribe({ next: (items) => this.customers.set(items) });
    this.api.coupons(establishmentId).subscribe({ next: (items) => this.coupons.set(items) });
    this.api.establishment(establishmentId).subscribe({ next: (store) => this.store.set(store) });
  }

  money(value: number | string | null | undefined): number {
    return Number(value ?? 0);
  }

  phone(value: string): string {
    return formatPhone(value);
  }

  whatsapp(value: string): string {
    return `https://wa.me/55${value.replace(/\D/g, '')}`;
  }

  onSearch(value: string): void {
    this.search.set(value);
    if (this.searchTimer) clearTimeout(this.searchTimer);
    this.searchTimer = setTimeout(() => {
      const establishment = this.tenant.current();
      if (establishment) this.api.customers(establishment.id, value).subscribe({ next: (items) => this.customers.set(items) });
    }, 250);
  }

  edit(customer: Customer): void {
    this.form = { name: customer.name, address: customer.address ?? '', neighborhood: customer.neighborhood ?? '', notes: customer.notes ?? '' };
    this.editing.set(customer);
  }

  saveCustomer(customer: Customer): void {
    const establishment = this.tenant.current();
    if (!establishment) return;
    this.api.updateCustomer(establishment.id, customer.id, {
      name: this.form.name.trim() || customer.name,
      address: this.form.address.trim() || null,
      neighborhood: this.form.neighborhood.trim() || null,
      notes: this.form.notes.trim() || null
    }).subscribe({
      next: (updated) => {
        this.customers.update((items) => items.map((item) => (item.id === updated.id ? updated : item)));
        this.editing.set(null);
      },
      error: (err) => this.toast.show('Erro', errorMessage(err, 'Nao foi possivel salvar.'), 'error')
    });
  }

  createCoupon(): void {
    const establishment = this.tenant.current();
    if (!establishment) return;
    this.api.createCoupon(establishment.id, {
      code: this.draft.code.trim(),
      kind: this.draft.kind,
      value: Number(this.draft.value),
      min_order: Number(this.draft.min_order) || 0,
      max_uses: this.draft.max_uses ? Number(this.draft.max_uses) : null,
      valid_until: this.draft.valid_until || null
    }).subscribe({
      next: (coupon) => {
        this.coupons.update((items) => [coupon, ...items]);
        this.draft = this.emptyDraft();
        this.toast.show('Cupom criado', coupon.code, 'success');
      },
      error: (err) => this.toast.show('Erro', errorMessage(err, 'Nao foi possivel criar o cupom.'), 'error')
    });
  }

  toggleCoupon(coupon: Coupon): void {
    const establishment = this.tenant.current();
    if (!establishment) return;
    this.api.updateCoupon(establishment.id, coupon.id, { active: !coupon.active }).subscribe({
      next: (updated) => this.coupons.update((items) => items.map((item) => (item.id === updated.id ? updated : item)))
    });
  }

  deleteCoupon(coupon: Coupon): void {
    const establishment = this.tenant.current();
    if (!establishment || !window.confirm(`Excluir o cupom ${coupon.code}?`)) return;
    this.api.deleteCoupon(establishment.id, coupon.id).subscribe({
      next: () => this.coupons.update((items) => items.filter((item) => item.id !== coupon.id))
    });
  }

  private emptyDraft(): CouponDraft {
    return { code: '', kind: 'PERCENT', value: null, min_order: null, max_uses: null, valid_until: '' };
  }
}
