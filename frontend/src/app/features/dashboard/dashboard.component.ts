import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, effect, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Activity, Banknote, CheckCircle2, CircleX, Clock3, RefreshCw, ShoppingBag, TrendingUp, LucideAngularModule } from 'lucide-angular';

import { ApiService } from '../../core/api.service';
import { DashboardResponse, OrderSource } from '../../core/models';
import { TenantService } from '../../core/tenant.service';
import { sourceClass, sourceLabel, statusClass, statusLabel } from '../../shared/status';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    LucideAngularModule
  ],
  template: `
    <section class="space-y-5">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 class="text-2xl font-extrabold tracking-normal text-zinc-950">Dashboard</h1>
          <p class="mt-1 text-sm text-zinc-500">Indicadores calculados com dados persistidos no PostgreSQL.</p>
        </div>
        <button class="focus-ring inline-flex h-10 items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 text-sm font-bold text-zinc-700 hover:bg-zinc-50" (click)="load()">
          <i-lucide name="refresh-cw" [size]="16" /> Atualizar
        </button>
      </div>

      @if (data(); as dashboard) {
        <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
          <article class="app-card p-4">
            <div class="flex items-center justify-between">
              <p class="text-sm font-semibold text-zinc-500">Recebidos hoje</p>
              <i-lucide class="text-brand-600" name="shopping-bag" [size]="19" />
            </div>
            <p class="mt-3 text-3xl font-extrabold tracking-normal">{{ dashboard.orders_today }}</p>
          </article>
          <article class="app-card p-4">
            <div class="flex items-center justify-between">
              <p class="text-sm font-semibold text-zinc-500">Em andamento</p>
              <i-lucide class="text-blue-600" name="activity" [size]="19" />
            </div>
            <p class="mt-3 text-3xl font-extrabold tracking-normal">{{ dashboard.in_progress }}</p>
          </article>
          <article class="app-card p-4">
            <div class="flex items-center justify-between">
              <p class="text-sm font-semibold text-zinc-500">Finalizados</p>
              <i-lucide class="text-emerald-600" name="check-circle-2" [size]="19" />
            </div>
            <p class="mt-3 text-3xl font-extrabold tracking-normal">{{ dashboard.finished_today }}</p>
          </article>
          <article class="app-card p-4">
            <div class="flex items-center justify-between">
              <p class="text-sm font-semibold text-zinc-500">Cancelados</p>
              <i-lucide class="text-red-600" name="circle-x" [size]="19" />
            </div>
            <p class="mt-3 text-3xl font-extrabold tracking-normal">{{ dashboard.canceled_today }}</p>
          </article>
          <article class="app-card p-4">
            <div class="flex items-center justify-between">
              <p class="text-sm font-semibold text-zinc-500">Faturamento</p>
              <i-lucide class="text-emerald-600" name="banknote" [size]="19" />
            </div>
            <p class="mt-3 text-2xl font-extrabold tracking-normal">{{ dashboard.gross_revenue_today | currency:'BRL':'symbol':'1.2-2' }}</p>
          </article>
          <article class="app-card p-4">
            <div class="flex items-center justify-between">
              <p class="text-sm font-semibold text-zinc-500">Ticket medio</p>
              <i-lucide class="text-indigo-600" name="trending-up" [size]="19" />
            </div>
            <p class="mt-3 text-2xl font-extrabold tracking-normal">{{ dashboard.average_ticket_today | currency:'BRL':'symbol':'1.2-2' }}</p>
          </article>
        </div>

        <div class="grid gap-5 xl:grid-cols-[1.15fr_0.85fr]">
          <article class="app-card p-5">
            <div class="mb-4 flex items-center justify-between">
              <div>
                <h2 class="text-lg font-extrabold text-zinc-950">Pedidos por horario</h2>
                <p class="text-sm text-zinc-500">Volume do dia atual, por hora no fuso da loja.</p>
              </div>
              <i-lucide class="text-zinc-400" name="clock-3" [size]="20" />
            </div>
            <div class="grid grid-cols-12 gap-2">
              @for (point of dashboard.orders_by_hour; track point.hour) {
                <div class="flex h-36 flex-col justify-end gap-2">
                  <div class="rounded-t bg-brand-500/80" [style.height]="barHeight(point.orders, maxHour(dashboard))"></div>
                  <span class="text-center text-[10px] font-semibold text-zinc-400">{{ point.hour }}</span>
                </div>
              }
            </div>
          </article>

          <article class="app-card p-5">
            <h2 class="text-lg font-extrabold text-zinc-950">Faturamento por canal</h2>
            <div class="mt-4 space-y-4">
              @for (channel of dashboard.sales_by_channel; track channel.source) {
                <div>
                  <div class="mb-2 flex items-center justify-between text-sm">
                    <span class="rounded-full px-2.5 py-1 font-bold ring-1" [ngClass]="sourceClass(channel.source)">{{ sourceLabel(channel.source) }}</span>
                    <span class="font-bold">{{ channel.total | currency:'BRL':'symbol':'1.2-2' }}</span>
                  </div>
                  <div class="h-2 rounded-full bg-zinc-100">
                    <div class="h-2 rounded-full bg-brand-500" [style.width]="barWidth(channel.total, maxChannel(dashboard))"></div>
                  </div>
                </div>
              } @empty {
                <p class="rounded-lg bg-zinc-50 p-4 text-sm text-zinc-500">Sem vendas registradas hoje.</p>
              }
            </div>
          </article>
        </div>

        <div class="grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
          <article class="app-card p-5">
            <h2 class="text-lg font-extrabold text-zinc-950">Ultimos sete dias</h2>
            <div class="mt-4 space-y-3">
              @for (day of dashboard.sales_last_7_days; track day.date) {
                <div class="grid grid-cols-[6rem_1fr_7rem] items-center gap-3 text-sm">
                  <span class="font-semibold text-zinc-500">{{ day.date | date:'dd/MM' }}</span>
                  <div class="h-2 rounded-full bg-zinc-100"><div class="h-2 rounded-full bg-emerald-500" [style.width]="barWidth(day.total, maxSales(dashboard))"></div></div>
                  <span class="text-right font-bold">{{ day.total | currency:'BRL':'symbol':'1.2-2' }}</span>
                </div>
              }
            </div>
          </article>

          <article class="app-card overflow-hidden">
            <div class="flex items-center justify-between border-b border-zinc-100 p-5">
              <div>
                <h2 class="text-lg font-extrabold text-zinc-950">Pedidos recentes</h2>
                <p class="text-sm text-zinc-500">Acompanhe as ultimas movimentacoes.</p>
              </div>
              <a class="rounded-lg border border-zinc-200 px-3 py-2 text-sm font-bold text-zinc-700 hover:bg-zinc-50" routerLink="/orders">Abrir central</a>
            </div>
            <div class="divide-y divide-zinc-100">
              @for (order of dashboard.recent_orders; track order.id) {
                <div class="grid gap-3 p-4 md:grid-cols-[1fr_auto] md:items-center">
                  <div>
                    <div class="flex flex-wrap items-center gap-2">
                      <p class="font-extrabold text-zinc-950">{{ order.order_number }}</p>
                      <span class="rounded-full px-2 py-0.5 text-xs font-bold ring-1" [ngClass]="sourceClass(order.source)">{{ sourceLabel(order.source) }}</span>
                      <span class="rounded-full px-2 py-0.5 text-xs font-bold ring-1" [ngClass]="statusClass(order.status)">{{ statusLabel(order.status) }}</span>
                    </div>
                    <p class="mt-1 text-sm text-zinc-500">{{ order.customer_name || 'Cliente nao informado' }} - {{ order.items.length }} itens</p>
                  </div>
                  <p class="text-right text-sm font-extrabold">{{ order.total | currency:'BRL':'symbol':'1.2-2' }}</p>
                </div>
              }
            </div>
          </article>
        </div>
      } @else {
        <div class="app-card p-6 text-sm font-semibold text-zinc-500">{{ loading() ? 'Carregando indicadores...' : 'Nenhum dado disponivel.' }}</div>
      }
    </section>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class DashboardComponent {
  private readonly api = inject(ApiService);
  private readonly tenant = inject(TenantService);

  readonly loading = signal(false);
  readonly data = signal<DashboardResponse | null>(null);

  constructor() {
    effect(() => {
      if (this.tenant.current()) {
        this.load();
      }
    }, { allowSignalWrites: true });
  }

  load(): void {
    const establishment = this.tenant.current();
    if (!establishment) return;
    this.loading.set(true);
    this.api.dashboard(establishment.id).subscribe({
      next: (response) => this.data.set(response),
      complete: () => this.loading.set(false),
      error: () => this.loading.set(false)
    });
  }

  sourceLabel = sourceLabel;
  sourceClass = sourceClass;
  statusLabel = statusLabel;
  statusClass = statusClass;

  maxHour(dashboard: DashboardResponse): number {
    return Math.max(1, ...dashboard.orders_by_hour.map((point) => point.orders));
  }

  maxChannel(dashboard: DashboardResponse): number {
    return Math.max(1, ...dashboard.sales_by_channel.map((point) => point.total));
  }

  maxSales(dashboard: DashboardResponse): number {
    return Math.max(1, ...dashboard.sales_last_7_days.map((point) => point.total));
  }

  barHeight(value: number, max: number): string {
    return `${Math.max(5, (value / max) * 100)}%`;
  }

  barWidth(value: number, max: number): string {
    return `${Math.max(2, (value / max) * 100)}%`;
  }
}
