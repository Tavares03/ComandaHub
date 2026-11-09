import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnDestroy, effect, inject, signal } from '@angular/core';
import { ChefHat, PackageCheck, Printer, RefreshCw, LucideAngularModule } from 'lucide-angular';

import { ApiService } from '../../core/api.service';
import { Order, OrderStatus } from '../../core/models';
import { TenantService } from '../../core/tenant.service';
import { ToastService } from '../../core/toast.service';
import { ItemOptionsComponent } from '../../shared/item-options.component';
import { sourceLabel, statusClass, statusLabel, waitLabel } from '../../shared/status';

@Component({
  selector: 'app-kitchen',
  standalone: true,
  imports: [CommonModule, LucideAngularModule, ItemOptionsComponent],
  template: `
    <section class="space-y-5">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 class="text-3xl font-extrabold tracking-normal text-zinc-950">Cozinha</h1>
          <p class="mt-1 text-sm text-zinc-500">Pedidos aceitos, em preparo e prontos para despacho.</p>
        </div>
        <button class="focus-ring inline-flex h-11 items-center gap-2 rounded-lg bg-zinc-950 px-4 text-sm font-extrabold text-white" (click)="load()">
          <i-lucide name="refresh-cw" [size]="18" /> Atualizar
        </button>
      </div>

      <div class="grid gap-4 xl:grid-cols-2 2xl:grid-cols-3">
        @for (order of kitchenOrders(); track order.id) {
          <article class="rounded-lg border-2 border-zinc-900 bg-white p-5 shadow-sm">
            <div class="flex items-start justify-between gap-3">
              <div>
                <p class="text-2xl font-extrabold text-zinc-950">{{ order.order_number }}</p>
                <p class="mt-1 text-sm font-bold text-zinc-500">{{ sourceLabel(order.source) }} - {{ waitLabel(order.created_at) }}</p>
              </div>
              <span class="rounded-full px-3 py-1 text-sm font-extrabold ring-1" [ngClass]="statusClass(order.status)">{{ statusLabel(order.status) }}</span>
            </div>

            <div class="mt-5 space-y-3">
              @for (item of order.items; track item.id) {
                <div class="rounded-lg bg-zinc-100 p-4">
                  <p class="text-xl font-extrabold text-zinc-950">{{ item.quantity }}x {{ item.product_name }}</p>
                  <app-item-options [options]="item.selected_options" size="lg" [highlight]="true" />
                  @if (item.notes) {
                    <p class="mt-2 rounded-md bg-amber-200 px-3 py-2 text-base font-extrabold text-amber-950">{{ item.notes }}</p>
                  }
                </div>
              }
            </div>

            @if (order.notes) {
              <p class="mt-4 rounded-lg bg-amber-100 p-4 text-lg font-extrabold text-amber-950">Obs: {{ order.notes }}</p>
            }

            <div class="mt-5 grid grid-cols-2 gap-3">
              @if (order.status === 'ACCEPTED') {
                <button class="focus-ring inline-flex h-12 items-center justify-center gap-2 rounded-lg bg-brand-500 text-base font-extrabold text-white" (click)="change(order, 'PREPARING')">
                  <i-lucide name="chef-hat" [size]="20" /> Iniciar
                </button>
              }
              @if (order.status === 'PREPARING') {
                <button class="focus-ring inline-flex h-12 items-center justify-center gap-2 rounded-lg bg-emerald-600 text-base font-extrabold text-white" (click)="change(order, 'READY')">
                  <i-lucide name="package-check" [size]="20" /> Pronto
                </button>
              }
              <button class="focus-ring inline-flex h-12 items-center justify-center gap-2 rounded-lg border border-zinc-300 text-base font-extrabold text-zinc-800" (click)="print(order)">
                <i-lucide name="printer" [size]="20" /> Imprimir
              </button>
            </div>
          </article>
        } @empty {
          <div class="app-card p-8 text-center text-sm font-semibold text-zinc-500">Nenhum pedido aguardando a cozinha.</div>
        }
      </div>
    </section>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class KitchenComponent implements OnDestroy {
  private readonly api = inject(ApiService);
  private readonly tenant = inject(TenantService);
  private readonly toast = inject(ToastService);
  private timerId: number | null = null;

  readonly orders = signal<Order[]>([]);

  constructor() {
    effect(() => {
      if (this.tenant.current()) {
        this.load();
      }
    }, { allowSignalWrites: true });
    this.timerId = window.setInterval(() => this.load(), 4000);
  }

  ngOnDestroy(): void {
    if (this.timerId) window.clearInterval(this.timerId);
  }

  load(): void {
    const establishment = this.tenant.current();
    if (!establishment) return;
    this.api.orderBoard(establishment.id).subscribe({ next: (response) => this.orders.set(response.items) });
  }

  kitchenOrders(): Order[] {
    return this.orders().filter((order) => ['ACCEPTED', 'PREPARING', 'READY'].includes(order.status));
  }

  change(order: Order, status: OrderStatus): void {
    const establishment = this.tenant.current();
    if (!establishment) return;
    this.api.updateOrderStatus(establishment.id, order.id, status).subscribe({
      next: (updated) => {
        this.orders.update((items) => items.map((item) => (item.id === updated.id ? updated : item)));
        this.toast.show('Cozinha atualizada', `${updated.order_number} esta ${statusLabel(updated.status).toLowerCase()}.`, 'success');
      },
      error: (err) => this.toast.show('Nao foi possivel alterar', err?.error?.detail ?? 'Transicao invalida.', 'error')
    });
  }

  print(_order: Order): void {
    window.print();
  }

  waitLabel = waitLabel;

  sourceLabel = sourceLabel;
  statusLabel = statusLabel;
  statusClass = statusClass;
}
