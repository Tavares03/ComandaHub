import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { LucideAngularModule } from 'lucide-angular';

import { ApiService } from '../../core/api.service';
import { OrderStatus, PublicOrderStatus } from '../../core/models';
import { paymentMethodLabel } from '../../shared/status';

interface Step {
  key: string;
  label: string;
  done: boolean;
  current: boolean;
}

/** Acompanhamento do pedido do cardapio online (link que o cliente recebe). */
@Component({
  selector: 'app-order-tracking',
  standalone: true,
  imports: [CommonModule, RouterLink, LucideAngularModule],
  template: `
    <div class="min-h-screen bg-zinc-50 px-4 py-8">
      <div class="mx-auto max-w-md space-y-4">
        @if (notFound()) {
          <div class="app-card p-8 text-center">
            <h1 class="text-xl font-extrabold text-zinc-950">Pedido nao encontrado</h1>
            <p class="mt-1 text-sm text-zinc-500">Confira o link do seu pedido.</p>
          </div>
        }
        @if (order(); as current) {
          <div class="app-card p-5 text-center">
            <p class="text-sm font-bold text-zinc-500">{{ current.store_name }}</p>
            <h1 class="mt-1 text-2xl font-extrabold text-zinc-950">Pedido {{ current.order_number }}</h1>
            <p class="mt-2 inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-extrabold"
               [ngClass]="current.status === 'CANCELED' ? 'bg-red-50 text-red-700' : current.status === 'FINISHED' ? 'bg-emerald-50 text-emerald-700' : 'bg-brand-50 text-brand-800'">
              {{ headline(current) }}
            </p>
          </div>

          @if (current.status !== 'CANCELED') {
            <ol class="app-card space-y-3 p-5">
              @for (step of steps(); track step.key) {
                <li class="flex items-center gap-3">
                  <span class="grid h-7 w-7 shrink-0 place-items-center rounded-full text-white" [ngClass]="step.done ? 'bg-emerald-600' : step.current ? 'bg-brand-500' : 'bg-zinc-200'">
                    @if (step.done) { <i-lucide name="check" [size]="15" /> }
                  </span>
                  <span class="text-sm" [ngClass]="step.current ? 'font-extrabold text-zinc-950' : step.done ? 'font-bold text-zinc-700' : 'text-zinc-400'">{{ step.label }}</span>
                </li>
              }
            </ol>
          }

          @if (current.store_whatsapp) {
            <a class="focus-ring flex h-12 items-center justify-center gap-2 rounded-xl bg-emerald-600 text-sm font-extrabold text-white hover:bg-emerald-700"
               [href]="whatsappLink(current)" target="_blank" rel="noopener">
              <i-lucide name="message-square" [size]="18" /> Enviar pedido no WhatsApp da loja
            </a>
          }

          <div class="app-card p-5 text-sm">
            <h2 class="font-extrabold text-zinc-950">Resumo</h2>
            <ul class="mt-2 space-y-2">
              @for (item of current.items; track $index) {
                <li class="flex justify-between gap-3">
                  <div>
                    <p class="font-bold">{{ item.quantity }}x {{ item.product_name }}</p>
                    @if (item.options.length) { <p class="text-xs text-zinc-500">{{ item.options.join(', ') }}</p> }
                  </div>
                  <span class="font-bold">{{ num(item.total) | currency:'BRL':'symbol':'1.2-2' }}</span>
                </li>
              }
            </ul>
            <div class="mt-3 space-y-1 border-t border-zinc-100 pt-3">
              @if (num(current.discount) > 0) {
                <div class="flex justify-between text-emerald-700"><span>Desconto</span><span>-{{ num(current.discount) | currency:'BRL':'symbol':'1.2-2' }}</span></div>
              }
              @if (num(current.delivery_fee) > 0) {
                <div class="flex justify-between text-zinc-500"><span>Entrega</span><span>{{ num(current.delivery_fee) | currency:'BRL':'symbol':'1.2-2' }}</span></div>
              }
              <div class="flex justify-between text-base font-extrabold"><span>Total ({{ payment(current) }})</span><span>{{ num(current.total) | currency:'BRL':'symbol':'1.2-2' }}</span></div>
            </div>
          </div>

          @if (current.store_slug) {
            <a class="block text-center text-sm font-bold text-brand-700 hover:underline" [routerLink]="['/cardapio', current.store_slug]">Voltar ao cardapio</a>
          }
        }
      </div>
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class OrderTrackingComponent implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);
  private timer: ReturnType<typeof setInterval> | null = null;
  private token = '';

  readonly order = signal<PublicOrderStatus | null>(null);
  readonly notFound = signal(false);

  readonly steps = computed<Step[]>(() => {
    const current = this.order();
    if (!current) return [];
    const delivery = current.fulfillment_type === 'DELIVERY';
    const flow: Array<{ key: OrderStatus; label: string }> = [
      { key: 'NEW', label: 'Pedido enviado' },
      { key: 'ACCEPTED', label: 'Loja aceitou' },
      { key: 'PREPARING', label: 'Em preparo' },
      ...(delivery
        ? [{ key: 'OUT_FOR_DELIVERY' as OrderStatus, label: 'Saiu para entrega' }]
        : [{ key: 'READY' as OrderStatus, label: 'Pronto para retirar' }]),
      { key: 'FINISHED', label: delivery ? 'Entregue' : 'Retirado' }
    ];
    const order: OrderStatus[] = ['NEW', 'ACCEPTED', 'PREPARING', 'READY', 'OUT_FOR_DELIVERY', 'FINISHED'];
    const reached = order.indexOf(current.status);
    return flow.map((step) => {
      const index = order.indexOf(step.key);
      return { key: step.key, label: step.label, done: index < reached || current.status === 'FINISHED', current: index === reached || (step.key === 'PREPARING' && current.status === 'READY' && delivery) };
    });
  });

  ngOnInit(): void {
    this.token = this.route.snapshot.paramMap.get('token') ?? '';
    this.load();
    this.timer = setInterval(() => this.load(), 15000);
  }

  ngOnDestroy(): void {
    if (this.timer) clearInterval(this.timer);
  }

  num(value: number | string | null | undefined): number {
    return Number(value ?? 0);
  }

  payment(order: PublicOrderStatus): string {
    return paymentMethodLabel(order.payment_method);
  }

  headline(order: PublicOrderStatus): string {
    const delivery = order.fulfillment_type === 'DELIVERY';
    return {
      NEW: 'Recebido - aguardando a loja',
      ACCEPTED: 'Aceito pela loja',
      PREPARING: 'Em preparo',
      READY: delivery ? 'Pronto - logo sai para entrega' : 'Pronto para retirar',
      OUT_FOR_DELIVERY: 'Saiu para entrega',
      FINISHED: delivery ? 'Entregue' : 'Retirado',
      CANCELED: 'Pedido cancelado'
    }[order.status];
  }

  whatsappLink(order: PublicOrderStatus): string {
    const lines = [
      `Ola! Fiz o pedido *${order.order_number}* pelo cardapio online.`,
      ...order.items.map((item) => `${item.quantity}x ${item.product_name}${item.options.length ? ' (' + item.options.join(', ') + ')' : ''}`),
      `Total: R$ ${this.num(order.total).toFixed(2).replace('.', ',')} (${this.payment(order)})`,
      order.delivery_address ? `Entrega: ${order.delivery_address}` : 'Vou retirar na loja',
      `Acompanhar: ${window.location.href}`
    ];
    return `https://wa.me/55${order.store_whatsapp}?text=${encodeURIComponent(lines.join('\n'))}`;
  }

  private load(): void {
    this.api.publicOrderStatus(this.token).subscribe({
      next: (order) => this.order.set(order),
      error: () => {
        if (!this.order()) this.notFound.set(true);
      }
    });
  }
}
