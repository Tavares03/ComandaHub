import { HttpParams } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, effect, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { BarChart3, CalendarDays, RefreshCw, Trophy, LucideAngularModule } from 'lucide-angular';

import { ApiService } from '../../core/api.service';
import { CourierReportRow, ProfitByChannel, ReportOverview, SalesChannel } from '../../core/models';
import { channelShort } from '../../shared/order-options';
import { TenantService } from '../../core/tenant.service';
import { sourceClass, sourceLabel } from '../../shared/status';

@Component({
  selector: 'app-reports',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, LucideAngularModule],
  template: `
    <section class="space-y-5">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 class="text-2xl font-extrabold tracking-normal text-zinc-950">Relatorios</h1>
          <p class="mt-1 text-sm text-zinc-500">Indicadores separados entre finalizados, cancelados e em andamento.</p>
        </div>
        <form class="flex flex-wrap items-end gap-2" [formGroup]="form" (ngSubmit)="load()">
          <label class="block">
            <span class="mb-1 block text-xs font-bold text-zinc-500">Inicio</span>
            <input class="focus-ring h-10 rounded-lg border border-zinc-200 px-3 text-sm" type="date" formControlName="start" />
          </label>
          <label class="block">
            <span class="mb-1 block text-xs font-bold text-zinc-500">Fim</span>
            <input class="focus-ring h-10 rounded-lg border border-zinc-200 px-3 text-sm" type="date" formControlName="end" />
          </label>
          <button class="focus-ring inline-flex h-10 items-center gap-2 rounded-lg bg-brand-500 px-3 text-sm font-extrabold text-white" type="submit">
            <i-lucide name="refresh-cw" [size]="16" /> Aplicar
          </button>
        </form>
      </div>

      @if (overview(); as data) {
        <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
          <article class="app-card p-4"><p class="text-sm font-semibold text-zinc-500">Total vendido</p><p class="mt-3 text-2xl font-extrabold">{{ data.total_sold | currency:'BRL':'symbol':'1.2-2' }}</p></article>
          <article class="app-card p-4"><p class="text-sm font-semibold text-zinc-500">Pedidos</p><p class="mt-3 text-3xl font-extrabold">{{ data.order_count }}</p></article>
          <article class="app-card p-4"><p class="text-sm font-semibold text-zinc-500">Ticket medio</p><p class="mt-3 text-2xl font-extrabold">{{ data.average_ticket | currency:'BRL':'symbol':'1.2-2' }}</p></article>
          <article class="app-card p-4"><p class="text-sm font-semibold text-zinc-500">Finalizados</p><p class="mt-3 text-3xl font-extrabold text-emerald-700">{{ data.finished_count }}</p></article>
          <article class="app-card p-4"><p class="text-sm font-semibold text-zinc-500">Em andamento</p><p class="mt-3 text-3xl font-extrabold text-blue-700">{{ data.in_progress_count }}</p></article>
          <article class="app-card p-4"><p class="text-sm font-semibold text-zinc-500">Cancelados</p><p class="mt-3 text-3xl font-extrabold text-red-700">{{ data.canceled_count }}</p></article>
        </div>
      }

      <div class="grid gap-5 xl:grid-cols-2">
        <article class="app-card p-5">
          <div class="mb-4 flex items-center gap-2">
            <i-lucide class="text-brand-600" name="bar-chart-3" [size]="20" />
            <h2 class="text-lg font-extrabold text-zinc-950">Faturamento por canal</h2>
          </div>
          <div class="space-y-3">
            @for (channel of channels(); track channel.source) {
              <div class="grid grid-cols-[8rem_1fr_7rem] items-center gap-3 text-sm">
                <span class="rounded-full px-2 py-1 text-xs font-bold ring-1" [ngClass]="sourceClass(channel.source)">{{ sourceLabel(channel.source) }}</span>
                <div class="h-2 rounded-full bg-zinc-100"><div class="h-2 rounded-full bg-brand-500" [style.width]="barWidth(channel.total, maxChannel())"></div></div>
                <span class="text-right font-bold">{{ channel.total | currency:'BRL':'symbol':'1.2-2' }}</span>
              </div>
            } @empty {
              <p class="rounded-lg bg-zinc-50 p-4 text-sm text-zinc-500">Sem vendas finalizadas no periodo.</p>
            }
          </div>
        </article>

        <article class="app-card p-5">
          <div class="mb-4 flex items-center gap-2">
            <i-lucide class="text-emerald-600" name="trophy" [size]="20" />
            <h2 class="text-lg font-extrabold text-zinc-950">Produtos mais vendidos</h2>
          </div>
          <div class="space-y-3">
            @for (product of topProducts(); track product.product_name) {
              <div class="grid grid-cols-[1fr_auto] gap-3 rounded-lg bg-zinc-50 p-3">
                <div>
                  <p class="font-bold">{{ product.product_name }}</p>
                  <p class="text-sm text-zinc-500">{{ product.quantity }} unidades</p>
                </div>
                <p class="font-extrabold">{{ product.total | currency:'BRL':'symbol':'1.2-2' }}</p>
              </div>
            } @empty {
              <p class="rounded-lg bg-zinc-50 p-4 text-sm text-zinc-500">Sem produtos vendidos no periodo.</p>
            }
          </div>
        </article>
      </div>

      <article class="app-card p-5">
        <div class="mb-1 flex items-center gap-2">
          <i-lucide class="text-brand-600" name="banknote" [size]="20" />
          <h2 class="text-lg font-extrabold text-zinc-950">Lucro por canal</h2>
        </div>
        <p class="mb-4 text-xs text-zinc-500">Vendas (sem cancelados) - comissao do app - custo dos ingredientes. Comissoes em Configuracoes; custo vem da ficha tecnica.</p>
        <div class="overflow-x-auto">
          <table class="w-full min-w-[640px] text-left text-sm">
            <thead class="text-xs uppercase text-zinc-500">
              <tr><th class="py-2">Canal</th><th>Pedidos</th><th>Vendas</th><th>Comissao</th><th>Ingredientes</th><th>Lucro bruto</th><th>Margem</th></tr>
            </thead>
            <tbody class="divide-y divide-zinc-100">
              @for (row of profit(); track row.channel) {
                <tr>
                  <td class="py-2.5 font-bold">{{ channelName(row.channel) }}</td>
                  <td>{{ row.orders }}</td>
                  <td class="font-bold">{{ num(row.revenue) | currency:'BRL':'symbol':'1.2-2' }}</td>
                  <td class="text-red-700">-{{ num(row.commission) | currency:'BRL':'symbol':'1.2-2' }} <span class="text-xs text-zinc-500">({{ num(row.commission_rate) }}%)</span></td>
                  <td class="text-red-700">-{{ num(row.ingredient_cost) | currency:'BRL':'symbol':'1.2-2' }}</td>
                  <td class="font-extrabold" [ngClass]="num(row.profit) >= 0 ? 'text-emerald-700' : 'text-red-700'">{{ num(row.profit) | currency:'BRL':'symbol':'1.2-2' }}</td>
                  <td class="font-bold">{{ num(row.margin) }}%</td>
                </tr>
              } @empty {
                <tr><td colspan="7" class="py-6 text-center text-zinc-500">Sem vendas no periodo.</td></tr>
              }
            </tbody>
          </table>
        </div>
      </article>

      <article class="app-card p-5">
        <div class="mb-4 flex items-center gap-2">
          <i-lucide class="text-brand-600" name="truck" [size]="20" />
          <h2 class="text-lg font-extrabold text-zinc-950">Entregas por motoboy</h2>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full min-w-[480px] text-left text-sm">
            <thead class="text-xs uppercase text-zinc-500">
              <tr><th class="py-2">Motoboy</th><th>Entregas</th><th>Taxas cobradas</th><th>A pagar</th></tr>
            </thead>
            <tbody class="divide-y divide-zinc-100">
              @for (row of couriers(); track row.courier_id) {
                <tr>
                  <td class="py-2.5 font-bold">{{ row.name }}</td>
                  <td>{{ row.deliveries }}</td>
                  <td>{{ num(row.fees_charged) | currency:'BRL':'symbol':'1.2-2' }}</td>
                  <td class="font-extrabold">{{ num(row.to_pay) | currency:'BRL':'symbol':'1.2-2' }}</td>
                </tr>
              } @empty {
                <tr><td colspan="4" class="py-6 text-center text-zinc-500">Nenhuma entrega com motoboy no periodo.</td></tr>
              }
            </tbody>
          </table>
        </div>
      </article>

      <div class="app-card p-4 text-sm text-zinc-500">
        <i-lucide class="mr-1 inline text-zinc-400" name="calendar-days" [size]="16" />
        Valores de marketplaces sao os valores registrados nos pedidos simulados, sem representar repasses liquidos reais.
      </div>
    </section>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class ReportsComponent {
  private readonly api = inject(ApiService);
  private readonly tenant = inject(TenantService);
  private readonly fb = inject(FormBuilder);

  readonly overview = signal<ReportOverview | null>(null);
  readonly channels = signal<Array<{ source: any; total: number; orders: number }>>([]);
  readonly topProducts = signal<Array<{ product_name: string; quantity: number; total: number }>>([]);
  readonly profit = signal<ProfitByChannel[]>([]);
  readonly couriers = signal<CourierReportRow[]>([]);
  readonly form = this.fb.nonNullable.group({
    start: [this.dateOffset(-7)],
    end: [this.dateOffset(0)]
  });

  constructor() {
    effect(() => {
      if (this.tenant.current()) this.load();
    }, { allowSignalWrites: true });
  }

  load(): void {
    const establishment = this.tenant.current();
    if (!establishment) return;
    const params = this.params();
    this.api.reportOverview(establishment.id, params).subscribe({ next: (data) => this.overview.set(data) });
    this.api.salesByChannel(establishment.id, params).subscribe({ next: (data) => this.channels.set(data) });
    this.api.topProducts(establishment.id, params).subscribe({ next: (data) => this.topProducts.set(data) });
    this.api.profitByChannel(establishment.id, params).subscribe({ next: (data) => this.profit.set(data) });
    this.api.courierReport(establishment.id, params).subscribe({ next: (data) => this.couriers.set(data) });
  }

  params(): HttpParams {
    const raw = this.form.getRawValue();
    return new HttpParams()
      .set('start', new Date(`${raw.start}T00:00:00`).toISOString())
      .set('end', new Date(`${raw.end}T23:59:59`).toISOString());
  }

  dateOffset(days: number): string {
    const date = new Date();
    date.setDate(date.getDate() + days);
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${date.getFullYear()}-${month}-${day}`;
  }

  num(value: number | string | null | undefined): number {
    return Number(value ?? 0);
  }

  channelName(channel: SalesChannel): string {
    return channel === 'LOCAL' ? 'Loja (balcao, retirada, delivery proprio)' : channelShort(channel) === '99' ? '99Food' : channelShort(channel);
  }

  maxChannel(): number {
    return Math.max(1, ...this.channels().map((item) => item.total));
  }

  barWidth(value: number, max: number): string {
    return `${Math.max(2, (value / max) * 100)}%`;
  }

  sourceClass = sourceClass;
  sourceLabel = sourceLabel;
}
