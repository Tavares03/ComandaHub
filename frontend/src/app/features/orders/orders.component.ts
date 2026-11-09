import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnDestroy, computed, effect, inject, signal } from '@angular/core';
import {
  Banknote,
  Ban,
  Check,
  ChefHat,
  Eye,
  PackageCheck,
  Printer,
  RefreshCw,
  Truck,
  Volume2,
  VolumeX,
  X,
  LucideAngularModule
} from 'lucide-angular';

import { ApiService } from '../../core/api.service';
import { Courier, FulfillmentType, Order, OrderStatus } from '../../core/models';
import { TenantService } from '../../core/tenant.service';
import { ToastService } from '../../core/toast.service';
import {
  ORDER_COLUMNS,
  fulfillmentLabel,
  nextStatuses,
  paymentMethodLabel,
  paymentStatusLabel,
  sourceClass,
  sourceLabel,
  statusClass,
  statusLabel,
  waitLabel
} from '../../shared/status';
import { ItemOptionsComponent } from '../../shared/item-options.component';

@Component({
  selector: 'app-orders',
  standalone: true,
  imports: [
    CommonModule,
    LucideAngularModule,
    ItemOptionsComponent
  ],
  template: `
    <section class="space-y-5">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 class="text-2xl font-extrabold tracking-normal text-zinc-950">Central de pedidos</h1>
          <p class="mt-1 text-sm text-zinc-500">Pedidos em andamento e encerrados hoje, com atualizacao automatica a cada 5 segundos.</p>
        </div>
        <div class="flex flex-wrap gap-2">
          <button class="focus-ring inline-flex h-10 items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 text-sm font-bold hover:bg-zinc-50" (click)="toggleSound()">
            <i-lucide [name]="soundEnabled() ? 'volume-2' : 'volume-x'" [size]="16" />
            Som
          </button>
          <button class="focus-ring inline-flex h-10 items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 text-sm font-bold hover:bg-zinc-50" (click)="toggleCanceled()">
            <i-lucide name="ban" [size]="16" />
            Cancelados
          </button>
          <button class="focus-ring inline-flex h-10 items-center gap-2 rounded-lg bg-brand-500 px-3 text-sm font-bold text-white hover:bg-brand-600" (click)="load(false)">
            <i-lucide name="refresh-cw" [size]="16" />
            Atualizar
          </button>
        </div>
      </div>

      @if (loading()) {
        <div class="app-card p-6 text-sm font-semibold text-zinc-500">Carregando pedidos...</div>
      }

      <div class="grid grid-flow-col auto-cols-[minmax(292px,1fr)] gap-4 overflow-x-auto pb-4">
        @for (column of columns; track column.status) {
          <section class="min-h-[68vh] rounded-lg border border-zinc-200 bg-zinc-100/70">
            <div class="sticky top-0 z-10 rounded-t-lg border-b border-zinc-200 bg-zinc-100/95 p-3 backdrop-blur">
              <div class="flex items-center justify-between">
                <div>
                  <h2 class="font-extrabold text-zinc-950">{{ column.title }}</h2>
                  <p class="text-xs font-medium text-zinc-500">{{ column.hint }}</p>
                </div>
                <span class="rounded-full bg-white px-2.5 py-1 text-xs font-extrabold text-zinc-700">{{ ordersByStatus(column.status).length }}</span>
              </div>
            </div>

            <div class="space-y-3 p-3">
              @for (order of ordersByStatus(column.status); track order.id) {
                <article class="app-card cursor-pointer p-3 transition hover:-translate-y-0.5 hover:shadow-md" (click)="openDetails(order)">
                  <div class="flex items-start justify-between gap-2">
                    <div>
                      <p class="font-extrabold text-zinc-950">{{ order.order_number }}</p>
                      <p class="text-xs font-semibold text-zinc-500">{{ waitLabel(order.created_at) }} na fila</p>
                    </div>
                    <span class="rounded-full px-2 py-0.5 text-[11px] font-extrabold ring-1" [ngClass]="sourceClass(order.source)">{{ sourceLabel(order.source) }}</span>
                  </div>

                  <p class="mt-3 text-sm font-bold text-zinc-800">{{ order.customer_name || 'Cliente nao informado' }}</p>
                  <div class="mt-2 space-y-1">
                    @for (item of order.items.slice(0, 3); track item.id) {
                      <p class="text-sm text-zinc-600">{{ item.quantity }}x {{ item.product_name }}</p>
                    }
                    @if (order.items.length > 3) {
                      <p class="text-xs font-semibold text-zinc-400">+ {{ order.items.length - 3 }} itens</p>
                    }
                  </div>

                  @if (order.notes) {
                    <div class="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800">{{ order.notes }}</div>
                  }

                  <div class="mt-3 flex items-center justify-between border-t border-zinc-100 pt-3">
                    <div>
                      <p class="text-xs font-semibold text-zinc-500">{{ fulfillmentLabel(order.fulfillment_type) }} - {{ paymentStatusLabel(order.payment_status) }}</p>
                      <p class="text-sm font-extrabold">{{ order.total | currency:'BRL':'symbol':'1.2-2' }}</p>
                    </div>
                    <button class="rounded-md border border-zinc-200 p-2 text-zinc-500 hover:bg-zinc-50" type="button" (click)="print(order); $event.stopPropagation()">
                      <i-lucide name="printer" [size]="16" />
                    </button>
                  </div>

                  <div class="mt-3 flex flex-wrap gap-2" (click)="$event.stopPropagation()">
                    @for (action of actions(order); track action) {
                      <button
                        class="focus-ring inline-flex h-8 items-center gap-1.5 rounded-md px-2.5 text-xs font-extrabold"
                        [ngClass]="actionClass(action)"
                        (click)="changeStatus(order, action)"
                      >
                        <i-lucide [name]="actionIcon(action)" [size]="14" />
                        {{ actionLabel(action) }}
                      </button>
                    }
                    <button class="focus-ring inline-flex h-8 items-center gap-1.5 rounded-md border border-zinc-200 px-2.5 text-xs font-extrabold text-zinc-600 hover:bg-zinc-50" (click)="openDetails(order)">
                      <i-lucide name="eye" [size]="14" />
                      Detalhes
                    </button>
                  </div>
                </article>
              } @empty {
                <div class="rounded-lg border border-dashed border-zinc-300 bg-white/70 p-5 text-center text-sm text-zinc-500">Nenhum pedido nesta etapa.</div>
              }
            </div>
          </section>
        }
      </div>

      @if (showCanceled()) {
        <section class="app-card p-4">
          <h2 class="text-lg font-extrabold text-zinc-950">Pedidos cancelados</h2>
          <div class="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            @for (order of ordersByStatus('CANCELED'); track order.id) {
              <button class="rounded-lg border border-red-100 bg-red-50 p-3 text-left" (click)="openDetails(order)">
                <p class="font-bold text-red-800">{{ order.order_number }} - {{ sourceLabel(order.source) }}</p>
                <p class="mt-1 text-sm text-red-700">{{ order.customer_name || 'Cliente nao informado' }}</p>
              </button>
            } @empty {
              <p class="text-sm text-zinc-500">Sem pedidos cancelados.</p>
            }
          </div>
        </section>
      }
    </section>

    @if (selectedOrder(); as order) {
      <div class="fixed inset-0 z-50 bg-zinc-950/30" (click)="selectedOrder.set(null)"></div>
      <aside class="fixed bottom-0 right-0 top-0 z-50 w-full overflow-y-auto bg-white shadow-2xl sm:w-[440px]" (click)="$event.stopPropagation()">
        <div class="sticky top-0 z-10 flex items-center justify-between border-b border-zinc-200 bg-white p-4">
          <div>
            <p class="text-xs font-bold uppercase text-zinc-400">Pedido</p>
            <h2 class="text-xl font-extrabold text-zinc-950">{{ order.order_number }}</h2>
          </div>
          <button class="rounded-md border border-zinc-200 p-2" (click)="selectedOrder.set(null)">
            <i-lucide name="x" [size]="18" />
          </button>
        </div>

        <div class="space-y-5 p-4">
          <div class="print-area thermal-ticket app-card p-4">
            <div class="mb-4 border-b border-dashed border-zinc-300 pb-3">
              <p class="text-lg font-extrabold">ComandaHub</p>
              <p class="text-sm font-bold">{{ order.order_number }} - {{ sourceLabel(order.source) }}</p>
              <p class="text-xs">{{ order.created_at | date:'dd/MM/yyyy HH:mm' }}</p>
            </div>
            <div class="space-y-2">
              @for (item of order.items; track item.id) {
                <div>
                  <p class="font-bold">{{ item.quantity }}x {{ item.product_name }}</p>
                  <app-item-options [options]="item.selected_options" size="ticket" />
                  @if (item.notes) {
                    <p class="text-xs font-bold">Obs: {{ item.notes }}</p>
                  }
                </div>
              }
            </div>
            @if (order.notes) {
              <p class="mt-4 border-t border-dashed border-zinc-300 pt-3 text-sm font-bold">Obs: {{ order.notes }}</p>
            }
          </div>

          <div class="flex flex-wrap gap-2">
            <span class="rounded-full px-2.5 py-1 text-xs font-bold ring-1" [ngClass]="sourceClass(order.source)">{{ sourceLabel(order.source) }}</span>
            <span class="rounded-full px-2.5 py-1 text-xs font-bold ring-1" [ngClass]="statusClass(order.status)">{{ statusLabel(order.status) }}</span>
            <span class="rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-bold text-zinc-700">{{ fulfillmentLabel(order.fulfillment_type) }}</span>
          </div>

          <div class="grid gap-3 rounded-lg bg-zinc-50 p-4 text-sm">
            <p><span class="font-bold">Cliente:</span> {{ order.customer_name || 'Nao informado' }}</p>
            <p><span class="font-bold">Telefone:</span> {{ order.customer_phone || 'Nao informado' }}</p>
            @if (order.delivery_address) {
              <p><span class="font-bold">Endereco:</span> {{ order.delivery_address }}{{ order.neighborhood ? ' - ' + order.neighborhood : '' }}</p>
            }
            @if (order.courier_name) {
              <p><span class="font-bold">Motoboy:</span> {{ order.courier_name }}</p>
            }
            @if (order.coupon_code) {
              <p><span class="font-bold">Cupom:</span> {{ order.coupon_code }}</p>
            }
            <div class="flex flex-wrap items-center justify-between gap-2">
              <p><span class="font-bold">Pagamento:</span> {{ paymentMethodLabel(order.payment_method) }} - {{ paymentStatusLabel(order.payment_status) }}</p>
              @if (order.payment_status === 'PENDING' && order.status !== 'CANCELED') {
                <button class="focus-ring inline-flex h-8 items-center gap-1.5 rounded-md bg-emerald-600 px-2.5 text-xs font-extrabold text-white hover:bg-emerald-700" (click)="markPaid(order)">
                  <i-lucide name="banknote" [size]="14" /> Marcar como pago
                </button>
              }
            </div>
          </div>

          <div>
            <h3 class="mb-3 font-extrabold text-zinc-950">Itens</h3>
            <div class="divide-y divide-zinc-100 rounded-lg border border-zinc-200">
              @for (item of order.items; track item.id) {
                <div class="p-3">
                  <div class="flex justify-between gap-3">
                    <p class="font-bold">{{ item.quantity }}x {{ item.product_name }}</p>
                    <p class="font-bold">{{ item.total | currency:'BRL':'symbol':'1.2-2' }}</p>
                  </div>
                  <app-item-options [options]="item.selected_options" />
                  @if (item.notes) {
                    <p class="mt-1 rounded bg-amber-50 px-2 py-1 text-xs font-semibold text-amber-800">{{ item.notes }}</p>
                  }
                </div>
              }
            </div>
          </div>

          <div class="rounded-lg border border-zinc-200 p-4 text-sm">
            <div class="flex justify-between"><span>Subtotal</span><strong>{{ order.subtotal | currency:'BRL':'symbol':'1.2-2' }}</strong></div>
            <div class="mt-2 flex justify-between"><span>Desconto</span><strong>{{ order.discount | currency:'BRL':'symbol':'1.2-2' }}</strong></div>
            <div class="mt-2 flex justify-between"><span>Entrega</span><strong>{{ order.delivery_fee | currency:'BRL':'symbol':'1.2-2' }}</strong></div>
            <div class="mt-3 flex justify-between border-t border-zinc-200 pt-3 text-base"><span>Total</span><strong>{{ order.total | currency:'BRL':'symbol':'1.2-2' }}</strong></div>
          </div>

          <div>
            <h3 class="mb-3 font-extrabold text-zinc-950">Historico</h3>
            <div class="space-y-2">
              @for (event of order.events; track event.id) {
                <div class="rounded-lg bg-zinc-50 p-3 text-sm">
                  <p class="font-bold">{{ event.event_type }}</p>
                  <p class="text-zinc-500">{{ event.created_at | date:'dd/MM/yyyy HH:mm:ss' }}</p>
                  @if (event.new_status) {
                    <p class="text-zinc-600">{{ event.previous_status || 'Inicio' }} -> {{ event.new_status }}</p>
                  }
                </div>
              }
            </div>
          </div>

          <div class="sticky bottom-0 -mx-4 flex flex-wrap gap-2 border-t border-zinc-200 bg-white p-4">
            @for (action of actions(order); track action) {
              <button class="focus-ring inline-flex h-10 items-center gap-2 rounded-lg px-3 text-sm font-extrabold" [ngClass]="actionClass(action)" (click)="changeStatus(order, action)">
                <i-lucide [name]="actionIcon(action)" [size]="16" /> {{ actionLabel(action) }}
              </button>
            }
            <button class="focus-ring inline-flex h-10 items-center gap-2 rounded-lg border border-zinc-200 px-3 text-sm font-extrabold text-zinc-700 hover:bg-zinc-50" (click)="print(order)">
              <i-lucide name="printer" [size]="16" /> Imprimir
            </button>
          </div>
        </div>
      </aside>
    }

    @if (courierPick(); as pending) {
      <div class="fixed inset-0 z-[60] bg-zinc-950/40" (click)="courierPick.set(null)"></div>
      <section class="fixed inset-x-0 bottom-0 z-[60] rounded-t-2xl bg-white p-5 shadow-2xl sm:inset-auto sm:left-1/2 sm:top-1/2 sm:w-[420px] sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-2xl"
               role="dialog" aria-modal="true" aria-label="Quem vai levar">
        <p class="text-xs font-bold uppercase text-brand-600">{{ pending.order_number }}</p>
        <h2 class="text-xl font-extrabold text-zinc-950">Quem vai levar?</h2>
        <div class="mt-4 grid gap-2">
          @for (courier of activeCouriers(); track courier.id) {
            <button type="button" class="focus-ring flex items-center justify-between rounded-lg border border-zinc-200 px-4 py-3 text-left text-sm font-bold hover:border-brand-500 hover:bg-brand-50"
                    (click)="changeStatus(pending, 'OUT_FOR_DELIVERY', courier.id)">
              <span class="inline-flex items-center gap-2"><i-lucide name="truck" [size]="16" /> {{ courier.name }}</span>
              <span class="text-xs font-normal text-zinc-500">{{ courier.phone }}</span>
            </button>
          }
          <button type="button" class="focus-ring rounded-lg px-4 py-2 text-sm font-bold text-zinc-600 hover:bg-zinc-50" (click)="changeStatus(pending, 'OUT_FOR_DELIVERY', null)">
            Enviar sem escolher motoboy
          </button>
        </div>
      </section>
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class OrdersComponent implements OnDestroy {
  private readonly api = inject(ApiService);
  private readonly tenant = inject(TenantService);
  private readonly toasts = inject(ToastService);
  private timerId: number | null = null;
  private knownIds = new Set<string>();
  private lastTenantId: string | null = null;

  readonly columns = ORDER_COLUMNS;
  readonly orders = signal<Order[]>([]);
  readonly loading = signal(false);
  readonly selectedOrder = signal<Order | null>(null);
  readonly showCanceled = signal(false);
  readonly soundEnabled = signal(false);
  readonly couriers = signal<Courier[]>([]);
  readonly activeCouriers = computed(() => this.couriers().filter((courier) => courier.active));
  /** Pedido esperando a escolha do motoboy */
  readonly courierPick = signal<Order | null>(null);

  constructor() {
    effect(() => {
      const establishment = this.tenant.current();
      if (establishment && establishment.id !== this.lastTenantId) {
        this.lastTenantId = establishment.id;
        this.knownIds.clear();
        this.load(false);
        this.api.couriers(establishment.id).subscribe({ next: (items) => this.couriers.set(items) });
      }
    }, { allowSignalWrites: true });
    this.timerId = window.setInterval(() => this.load(true), 5000);
  }

  ngOnDestroy(): void {
    if (this.timerId) {
      window.clearInterval(this.timerId);
    }
  }

  load(showNotifications: boolean): void {
    const establishment = this.tenant.current();
    if (!establishment) return;
    this.loading.set(!showNotifications);
    this.api.orderBoard(establishment.id).subscribe({
      next: (response) => {
        const incoming = response.items;
        if (showNotifications && this.knownIds.size) {
          const newOrders = incoming.filter((order) => !this.knownIds.has(order.id) && order.status === 'NEW');
          if (newOrders.length) {
            this.toasts.show('Novo pedido recebido', `${newOrders.length} pedido(s) apareceram na central.`, 'success');
            this.beep();
          }
        }
        this.knownIds = new Set(incoming.map((order) => order.id));
        this.orders.set(incoming);
        const selected = this.selectedOrder();
        if (selected) {
          this.selectedOrder.set(incoming.find((order) => order.id === selected.id) ?? selected);
        }
      },
      error: () => this.toasts.show('Erro ao carregar pedidos', 'Tente atualizar novamente em alguns segundos.', 'error'),
      complete: () => this.loading.set(false)
    });
  }

  toggleCanceled(): void {
    this.showCanceled.update((value) => !value);
  }

  ordersByStatus(status: OrderStatus): Order[] {
    return this.orders().filter((order) => order.status === status);
  }

  openDetails(order: Order): void {
    const establishment = this.tenant.current();
    if (!establishment) return;
    this.api.order(establishment.id, order.id).subscribe({
      next: (detail) => this.selectedOrder.set(detail),
      error: () => this.selectedOrder.set(order)
    });
  }

  actions(order: Order): OrderStatus[] {
    return nextStatuses(order.status, order.fulfillment_type);
  }

  /** Ao sair para entrega, pergunta qual motoboy levou (se houver motoboys cadastrados). */
  changeStatus(order: Order, status: OrderStatus, courierId?: string | null): void {
    const establishment = this.tenant.current();
    if (!establishment) return;
    if (status === 'OUT_FOR_DELIVERY' && courierId === undefined && this.activeCouriers().length) {
      this.courierPick.set(order);
      return;
    }
    this.courierPick.set(null);
    let reason: string | undefined;
    if (status === 'CANCELED') {
      const typed = window.prompt('Informe o motivo do cancelamento');
      if (!typed) return;
      reason = typed;
    }
    this.api.updateOrderStatus(establishment.id, order.id, status, reason, courierId).subscribe({
      next: (updated) => {
        this.orders.update((items) => items.map((item) => (item.id === updated.id ? updated : item)));
        if (this.selectedOrder()?.id === updated.id) {
          this.selectedOrder.set(updated);
        }
        this.toasts.show('Pedido atualizado', `${updated.order_number} agora esta ${statusLabel(updated.status).toLowerCase()}.`, 'success');
      },
      error: (err) => this.toasts.show('Acao recusada', err?.error?.detail ?? 'Transicao de status invalida.', 'error')
    });
  }

  markPaid(order: Order): void {
    const establishment = this.tenant.current();
    if (!establishment) return;
    this.api.updatePaymentStatus(establishment.id, order.id, 'PAID').subscribe({
      next: (updated) => {
        this.orders.update((items) => items.map((item) => (item.id === updated.id ? updated : item)));
        this.selectedOrder.set(updated);
        this.toasts.show('Pagamento registrado', `${updated.order_number} marcado como pago.`, 'success');
      },
      error: (err) => this.toasts.show('Nao foi possivel registrar', err?.error?.detail ?? 'Tente novamente.', 'error')
    });
  }

  print(order: Order): void {
    this.openDetails(order);
    window.setTimeout(() => window.print(), 220);
  }

  toggleSound(): void {
    this.soundEnabled.update((value) => !value);
    if (this.soundEnabled()) {
      this.beep();
    }
  }

  beep(): void {
    if (!this.soundEnabled()) return;
    const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const context = new AudioContextClass();
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.type = 'sine';
    oscillator.frequency.value = 880;
    gain.gain.value = 0.08;
    oscillator.connect(gain);
    gain.connect(context.destination);
    oscillator.start();
    window.setTimeout(() => {
      oscillator.stop();
      void context.close();
    }, 160);
  }

  waitLabel = waitLabel;

  actionLabel(status: OrderStatus): string {
    return {
      ACCEPTED: 'Aceitar',
      PREPARING: 'Iniciar',
      READY: 'Pronto',
      OUT_FOR_DELIVERY: 'Enviar',
      FINISHED: 'Finalizar',
      CANCELED: 'Cancelar',
      NEW: 'Novo'
    }[status];
  }

  actionIcon(status: OrderStatus): string {
    return {
      ACCEPTED: 'check',
      PREPARING: 'chef-hat',
      READY: 'package-check',
      OUT_FOR_DELIVERY: 'truck',
      FINISHED: 'check',
      CANCELED: 'ban',
      NEW: 'eye'
    }[status];
  }

  actionClass(status: OrderStatus): string {
    if (status === 'CANCELED') return 'bg-red-50 text-red-700 hover:bg-red-100';
    if (status === 'FINISHED') return 'bg-zinc-900 text-white hover:bg-zinc-800';
    return 'bg-brand-500 text-white hover:bg-brand-600';
  }

  sourceLabel = sourceLabel;
  sourceClass = sourceClass;
  statusLabel = statusLabel;
  statusClass = statusClass;
  fulfillmentLabel = fulfillmentLabel;
  paymentMethodLabel = paymentMethodLabel;
  paymentStatusLabel = paymentStatusLabel;
}
