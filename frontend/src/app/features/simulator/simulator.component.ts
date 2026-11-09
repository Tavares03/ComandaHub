import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FlaskConical, LoaderCircle, Plus, Zap, LucideAngularModule } from 'lucide-angular';

import { ApiService } from '../../core/api.service';
import { Order, OrderSource } from '../../core/models';
import { TenantService } from '../../core/tenant.service';
import { ToastService } from '../../core/toast.service';
import { sourceClass, sourceLabel } from '../../shared/status';

@Component({
  selector: 'app-simulator',
  standalone: true,
  imports: [CommonModule, LucideAngularModule],
  template: `
    <section class="space-y-5">
      <div>
        <h1 class="text-2xl font-extrabold tracking-normal text-zinc-950">Laboratorio de pedidos</h1>
        <p class="mt-1 text-sm text-zinc-500">Crie pedidos ficticios sem depender de credenciais oficiais de marketplaces.</p>
      </div>

      <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        @for (source of sources; track source.value) {
          <button class="app-card p-5 text-left transition hover:-translate-y-0.5 hover:shadow-md" [disabled]="loading()" (click)="simulate(source.value, 1)">
            <span class="mb-4 inline-flex rounded-full px-3 py-1 text-xs font-extrabold ring-1" [ngClass]="sourceClass(source.value)">{{ source.label }}</span>
            <p class="text-lg font-extrabold text-zinc-950">Simular pedido</p>
            <p class="mt-2 text-sm text-zinc-500">{{ source.description }}</p>
            <span class="mt-4 inline-flex h-9 items-center gap-2 rounded-lg bg-brand-500 px-3 text-sm font-bold text-white">
              <i-lucide name="plus" [size]="16" /> Criar
            </span>
          </button>
        }
      </div>

      <button class="focus-ring inline-flex h-11 items-center gap-2 rounded-lg bg-zinc-950 px-4 text-sm font-extrabold text-white" [disabled]="loading()" (click)="simulate('IFOOD', 5)">
        @if (loading()) {
          <i-lucide class="animate-spin" name="loader-circle" [size]="17" />
        } @else {
          <i-lucide name="zap" [size]="17" />
        }
        Simular multiplos pedidos
      </button>

      <article class="app-card overflow-hidden">
        <div class="border-b border-zinc-100 p-4">
          <div class="flex items-center gap-2">
            <i-lucide class="text-brand-600" name="flask-conical" [size]="20" />
            <h2 class="text-lg font-extrabold text-zinc-950">Ultimos pedidos criados</h2>
          </div>
        </div>
        <div class="divide-y divide-zinc-100">
          @for (order of created(); track order.id) {
            <div class="grid gap-2 p-4 sm:grid-cols-[1fr_auto] sm:items-center">
              <div>
                <p class="font-extrabold">{{ order.order_number }}</p>
                <p class="text-sm text-zinc-500">{{ order.customer_name || 'Cliente demo' }}</p>
              </div>
              <span class="w-max rounded-full px-2.5 py-1 text-xs font-bold ring-1" [ngClass]="sourceClass(order.source)">{{ sourceLabel(order.source) }}</span>
            </div>
          } @empty {
            <p class="p-5 text-sm text-zinc-500">Nenhuma simulacao nesta sessao.</p>
          }
        </div>
      </article>
    </section>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class SimulatorComponent {
  private readonly api = inject(ApiService);
  private readonly tenant = inject(TenantService);
  private readonly toast = inject(ToastService);

  readonly loading = signal(false);
  readonly created = signal<Order[]>([]);
  readonly sources: Array<{ value: OrderSource; label: string; description: string }> = [
    { value: 'IFOOD', label: 'iFood', description: 'Pedido marketplace em modo demonstracao.' },
    { value: 'NINETY_NINE_FOOD', label: '99Food', description: 'Pedido externo normalizado pelo conector simulado.' },
    { value: 'OWN_DELIVERY', label: 'Delivery proprio', description: 'Pedido do canal direto da loja.' },
    { value: 'COUNTER', label: 'Balcao', description: 'Pedido presencial para acompanhar no fluxo.' }
  ];

  simulate(source: OrderSource, quantity: number): void {
    const establishment = this.tenant.current();
    if (!establishment) return;
    this.loading.set(true);
    this.api.simulateOrder(establishment.id, source, quantity).subscribe({
      next: (orders) => {
        this.created.update((items) => [...orders, ...items]);
        this.toast.show('Pedido simulado', `${orders.length} pedido(s) criados no banco.`, 'success');
      },
      error: (err) => this.toast.show('Simulacao falhou', err?.error?.detail ?? 'Nao foi possivel criar o pedido.', 'error'),
      complete: () => this.loading.set(false)
    });
  }

  sourceClass = sourceClass;
  sourceLabel = sourceLabel;
}
