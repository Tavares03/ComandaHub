import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, effect, inject, signal, untracked } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { LucideAngularModule } from 'lucide-angular';

import { ApiService } from '../../core/api.service';
import { Courier, DeliveryZone, SalesChannel } from '../../core/models';
import { TenantService } from '../../core/tenant.service';
import { ToastService } from '../../core/toast.service';
import { CHANNELS, errorMessage } from '../../shared/order-options';

/** Bairros e taxas, motoboys, fidelidade e comissao por canal. */
@Component({
  selector: 'app-operations-settings',
  standalone: true,
  imports: [CommonModule, FormsModule, LucideAngularModule],
  template: `
    <div class="grid gap-5 2xl:grid-cols-2">
      <article class="app-card p-5 2xl:col-span-2">
        <div class="mb-1 flex items-center gap-2">
          <i-lucide class="text-brand-600" name="store" [size]="20" />
          <h2 class="text-lg font-extrabold text-zinc-950">Cardapio online</h2>
        </div>
        <p class="mb-4 text-xs text-zinc-500">Link para o cliente pedir sozinho (entrega ou retirada). O pedido cai na Central como delivery proprio, sem comissao.</p>
        <div class="flex flex-wrap gap-x-6 gap-y-2">
          <label class="flex items-center gap-2 text-sm font-bold text-zinc-700">
            <input type="checkbox" [(ngModel)]="online.enabled" /> Cardapio online no ar
          </label>
          <label class="flex items-center gap-2 text-sm font-bold text-zinc-700" title="Desmarque para fechar a loja: o cardapio continua visivel, mas ninguem consegue pedir">
            <input type="checkbox" [(ngModel)]="online.open" [disabled]="!online.enabled" /> Recebendo pedidos agora (loja aberta)
          </label>
        </div>
        <div class="mt-3 grid gap-3 md:grid-cols-2">
          <label class="block">
            <span class="mb-1 block text-xs font-bold text-zinc-500">Endereco do link</span>
            <div class="flex items-center rounded-lg border border-zinc-200 bg-zinc-50 pl-3 text-sm text-zinc-500">
              <span class="whitespace-nowrap">/cardapio/</span>
              <input class="focus-ring h-10 min-w-0 flex-1 rounded-r-lg border-l border-zinc-200 bg-white px-2 text-sm text-zinc-900" [(ngModel)]="online.slug" placeholder="minha-loja" />
            </div>
          </label>
          <label class="block">
            <span class="mb-1 block text-xs font-bold text-zinc-500">WhatsApp da loja (com DDD)</span>
            <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" [(ngModel)]="online.whatsapp" placeholder="11999999999" inputmode="tel" />
          </label>
        </div>
        @if (online.slug) {
          <div class="mt-3 flex flex-wrap items-center gap-2 rounded-lg bg-zinc-50 p-3 text-sm">
            <span class="min-w-0 flex-1 truncate font-mono text-zinc-700">{{ publicLink() }}</span>
            <button type="button" class="focus-ring inline-flex h-9 items-center gap-1 rounded-md border border-zinc-200 bg-white px-3 text-sm font-bold hover:bg-zinc-50" (click)="copyLink()">Copiar link</button>
            <a class="focus-ring inline-flex h-9 items-center gap-1 rounded-md border border-zinc-200 bg-white px-3 text-sm font-bold hover:bg-zinc-50" [href]="publicLink()" target="_blank" rel="noopener">Abrir</a>
          </div>
        }
        <button class="focus-ring mt-4 inline-flex h-10 items-center gap-2 rounded-lg bg-brand-500 px-4 text-sm font-extrabold text-white hover:bg-brand-600 disabled:opacity-50"
                [disabled]="saving()" (click)="saveOnline()">
          <i-lucide name="save" [size]="16" /> Salvar cardapio online
        </button>
      </article>

      <article class="app-card p-5">
        <div class="mb-4 flex items-center gap-2">
          <i-lucide class="text-brand-600" name="truck" [size]="20" />
          <h2 class="text-lg font-extrabold text-zinc-950">Bairros e taxas de entrega</h2>
        </div>
        <div class="space-y-2">
          @for (zone of zones(); track zone.id) {
            <div class="grid grid-cols-[1fr_96px_80px_auto_auto] items-center gap-2">
              <input class="focus-ring h-9 min-w-0 rounded-md border border-zinc-200 px-2 text-sm" [(ngModel)]="zone.name" (change)="saveZone(zone)" [attr.aria-label]="'Nome do bairro'" />
              <label class="flex items-center gap-1 text-xs text-zinc-500">R$
                <input class="focus-ring h-9 w-full min-w-0 rounded-md border border-zinc-200 px-2 text-sm" type="number" step="0.01" min="0" [(ngModel)]="zone.fee" (change)="saveZone(zone)" aria-label="Taxa" />
              </label>
              <label class="flex items-center gap-1 text-xs text-zinc-500">
                <input class="focus-ring h-9 w-full min-w-0 rounded-md border border-zinc-200 px-2 text-sm" type="number" min="1" [(ngModel)]="zone.estimated_minutes" (change)="saveZone(zone)" aria-label="Tempo em minutos" />min
              </label>
              <label class="flex items-center gap-1 text-xs font-bold text-zinc-600"><input type="checkbox" [(ngModel)]="zone.active" (change)="saveZone(zone)" /> Ativo</label>
              <button class="focus-ring rounded p-1.5 text-red-600 hover:bg-red-50" (click)="deleteZone(zone)" [attr.aria-label]="'Excluir ' + zone.name"><i-lucide name="trash-2" [size]="15" /></button>
            </div>
          } @empty {
            <p class="text-sm text-zinc-500">Nenhum bairro cadastrado.</p>
          }
          <form class="grid grid-cols-[1fr_96px_auto] gap-2 border-t border-zinc-100 pt-3" (ngSubmit)="addZone()">
            <input class="focus-ring h-9 rounded-md border border-zinc-200 px-2 text-sm" name="zoneName" placeholder="Novo bairro" [(ngModel)]="newZone.name" />
            <input class="focus-ring h-9 rounded-md border border-zinc-200 px-2 text-sm" name="zoneFee" type="number" step="0.01" min="0" placeholder="Taxa" [(ngModel)]="newZone.fee" />
            <button class="focus-ring inline-flex h-9 items-center gap-1 rounded-md bg-brand-500 px-3 text-sm font-bold text-white disabled:opacity-50" type="submit" [disabled]="newZone.name.trim().length < 2">
              <i-lucide name="plus" [size]="15" /> Bairro
            </button>
          </form>
        </div>
      </article>

      <article class="app-card p-5">
        <div class="mb-1 flex items-center gap-2">
          <i-lucide class="text-brand-600" name="users" [size]="20" />
          <h2 class="text-lg font-extrabold text-zinc-950">Motoboys</h2>
        </div>
        <p class="mb-4 text-xs text-zinc-500">"Por entrega" = quanto ele recebe por corrida. Vazio/0 = recebe a taxa cobrada do cliente.</p>
        <div class="space-y-2">
          @for (courier of couriers(); track courier.id) {
            <div class="grid grid-cols-[1fr_130px_90px_auto_auto] items-center gap-2">
              <input class="focus-ring h-9 min-w-0 rounded-md border border-zinc-200 px-2 text-sm" [(ngModel)]="courier.name" (change)="saveCourier(courier)" aria-label="Nome" />
              <input class="focus-ring h-9 min-w-0 rounded-md border border-zinc-200 px-2 text-sm" [(ngModel)]="courier.phone" (change)="saveCourier(courier)" placeholder="Telefone" aria-label="Telefone" />
              <input class="focus-ring h-9 min-w-0 rounded-md border border-zinc-200 px-2 text-sm" type="number" step="0.01" min="0" [(ngModel)]="courier.fee_per_delivery" (change)="saveCourier(courier)" aria-label="Por entrega" />
              <label class="flex items-center gap-1 text-xs font-bold text-zinc-600"><input type="checkbox" [(ngModel)]="courier.active" (change)="saveCourier(courier)" /> Ativo</label>
              <button class="focus-ring rounded p-1.5 text-red-600 hover:bg-red-50" (click)="deleteCourier(courier)" [attr.aria-label]="'Excluir ' + courier.name"><i-lucide name="trash-2" [size]="15" /></button>
            </div>
          } @empty {
            <p class="text-sm text-zinc-500">Nenhum motoboy cadastrado.</p>
          }
          <form class="grid grid-cols-[1fr_130px_auto] gap-2 border-t border-zinc-100 pt-3" (ngSubmit)="addCourier()">
            <input class="focus-ring h-9 rounded-md border border-zinc-200 px-2 text-sm" name="courierName" placeholder="Nome do motoboy" [(ngModel)]="newCourier.name" />
            <input class="focus-ring h-9 rounded-md border border-zinc-200 px-2 text-sm" name="courierPhone" placeholder="Telefone" [(ngModel)]="newCourier.phone" />
            <button class="focus-ring inline-flex h-9 items-center gap-1 rounded-md bg-brand-500 px-3 text-sm font-bold text-white disabled:opacity-50" type="submit" [disabled]="newCourier.name.trim().length < 2">
              <i-lucide name="plus" [size]="15" /> Motoboy
            </button>
          </form>
        </div>
      </article>

      <article class="app-card p-5">
        <div class="mb-4 flex items-center gap-2">
          <i-lucide class="text-brand-600" name="trophy" [size]="20" />
          <h2 class="text-lg font-extrabold text-zinc-950">Fidelidade</h2>
        </div>
        <label class="flex items-center gap-2 text-sm font-bold text-zinc-700">
          <input type="checkbox" [(ngModel)]="loyalty.enabled" /> Programa de fidelidade ligado
        </label>
        <div class="mt-3 grid grid-cols-2 gap-3">
          <label class="block">
            <span class="mb-1 block text-xs font-bold text-zinc-500">A cada quantos pedidos</span>
            <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" type="number" min="1" [(ngModel)]="loyalty.goal" />
          </label>
          <label class="block">
            <span class="mb-1 block text-xs font-bold text-zinc-500">Desconto no proximo (R$)</span>
            <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" type="number" step="0.01" min="0" [(ngModel)]="loyalty.reward" />
          </label>
        </div>
        <p class="mt-2 text-xs text-zinc-500">Cada pedido finalizado com telefone vale 1 ponto (balcao, retirada, delivery proprio e cardapio online). O resgate da recompensa e feito pelo atendente no Pedido local.</p>
      </article>

      <article class="app-card p-5">
        <div class="mb-1 flex items-center gap-2">
          <i-lucide class="text-brand-600" name="bar-chart-3" [size]="20" />
          <h2 class="text-lg font-extrabold text-zinc-950">Comissao por canal</h2>
        </div>
        <p class="mb-4 text-xs text-zinc-500">Quanto cada app cobra (%). Usado no relatorio de lucro por canal.</p>
        <div class="grid grid-cols-3 gap-3">
          @for (channel of channels; track channel.id) {
            <label class="block">
              <span class="mb-1 block text-xs font-bold text-zinc-500">{{ channel.short }} (%)</span>
              <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" type="number" step="0.1" min="0" max="100"
                     [ngModel]="commissions[channel.id]" (ngModelChange)="commissions[channel.id] = $event" />
            </label>
          }
        </div>
        <button class="focus-ring mt-4 inline-flex h-10 items-center gap-2 rounded-lg bg-brand-500 px-4 text-sm font-extrabold text-white hover:bg-brand-600 disabled:opacity-50"
                [disabled]="saving()" (click)="saveSettings()">
          <i-lucide name="save" [size]="16" /> Salvar fidelidade e comissoes
        </button>
      </article>
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class OperationsSettingsComponent {
  private readonly api = inject(ApiService);
  private readonly tenant = inject(TenantService);
  private readonly toast = inject(ToastService);

  readonly channels = CHANNELS;
  readonly zones = signal<DeliveryZone[]>([]);
  readonly couriers = signal<Courier[]>([]);
  readonly saving = signal(false);
  newZone = { name: '', fee: null as number | null };
  newCourier = { name: '', phone: '' };
  loyalty = { enabled: false, goal: 10, reward: 15 };
  online = { enabled: false, open: true, slug: '', whatsapp: '' };
  commissions: Partial<Record<SalesChannel, number | null>> = {};

  constructor() {
    effect(() => {
      const establishment = this.tenant.current();
      if (establishment) untracked(() => this.load(establishment.id));
    }, { allowSignalWrites: true });
  }

  load(establishmentId: string): void {
    this.api.deliveryZones(establishmentId).subscribe({ next: (items) => this.zones.set(items) });
    this.api.couriers(establishmentId).subscribe({ next: (items) => this.couriers.set(items) });
    this.api.establishment(establishmentId).subscribe({
      next: (store) => {
        this.loyalty = { enabled: store.loyalty_enabled, goal: store.loyalty_goal, reward: Number(store.loyalty_reward) };
        this.online = { enabled: store.online_menu_enabled, open: store.online_orders_open, slug: store.slug ?? '', whatsapp: store.whatsapp ?? '' };
        this.commissions = {};
        for (const channel of CHANNELS) {
          const value = store.channel_commissions?.[channel.id];
          this.commissions[channel.id] = value === undefined || value === null ? null : Number(value);
        }
        this.zones.set([...this.zones()]);
      }
    });
  }

  publicLink(): string {
    return `${window.location.origin}/cardapio/${this.online.slug.trim().toLowerCase()}`;
  }

  copyLink(): void {
    navigator.clipboard?.writeText(this.publicLink()).then(
      () => this.toast.show('Link copiado', 'Mande para os clientes ou coloque na bio.', 'success'),
      () => this.toast.show('Nao deu para copiar', this.publicLink(), 'info')
    );
  }

  saveOnline(): void {
    const establishment = this.tenant.current();
    if (!establishment) return;
    this.saving.set(true);
    this.api.updateEstablishment(establishment.id, {
      online_menu_enabled: this.online.enabled,
      online_orders_open: this.online.open,
      slug: this.online.slug.trim().toLowerCase() || null,
      whatsapp: this.online.whatsapp.trim() || null
    }).subscribe({
      next: () => {
        this.saving.set(false);
        const status = !this.online.enabled ? 'O link esta desligado.' : this.online.open ? 'O link esta no ar e recebendo pedidos.' : 'O link esta no ar, com a loja fechada.';
        this.toast.show('Cardapio online salvo', status, 'success');
      },
      error: (err) => {
        this.saving.set(false);
        this.toast.show('Erro', errorMessage(err, 'Nao foi possivel salvar (o endereco pode ja estar em uso).'), 'error');
      }
    });
  }

  addZone(): void {
    const establishment = this.tenant.current();
    if (!establishment) return;
    this.api.saveDeliveryZone(establishment.id, { name: this.newZone.name.trim(), fee: Number(this.newZone.fee) || 0, active: true }).subscribe({
      next: (zone) => {
        this.zones.update((items) => [...items, zone].sort((a, b) => a.name.localeCompare(b.name)));
        this.newZone = { name: '', fee: null };
      },
      error: (err) => this.toast.show('Erro', errorMessage(err, 'Nao foi possivel criar o bairro.'), 'error')
    });
  }

  saveZone(zone: DeliveryZone): void {
    const establishment = this.tenant.current();
    if (!establishment || zone.name.trim().length < 2) return;
    this.api.saveDeliveryZone(establishment.id, {
      id: zone.id,
      name: zone.name.trim(),
      fee: Number(zone.fee) || 0,
      estimated_minutes: zone.estimated_minutes ? Number(zone.estimated_minutes) : null,
      active: zone.active
    }).subscribe({ error: (err) => this.toast.show('Erro', errorMessage(err, 'Nao foi possivel salvar o bairro.'), 'error') });
  }

  deleteZone(zone: DeliveryZone): void {
    const establishment = this.tenant.current();
    if (!establishment || !window.confirm(`Excluir o bairro ${zone.name}?`)) return;
    this.api.deleteDeliveryZone(establishment.id, zone.id).subscribe({ next: () => this.zones.update((items) => items.filter((item) => item.id !== zone.id)) });
  }

  addCourier(): void {
    const establishment = this.tenant.current();
    if (!establishment) return;
    this.api.saveCourier(establishment.id, { name: this.newCourier.name.trim(), phone: this.newCourier.phone.trim() || null, fee_per_delivery: 0, active: true }).subscribe({
      next: (courier) => {
        this.couriers.update((items) => [...items, courier]);
        this.newCourier = { name: '', phone: '' };
      },
      error: (err) => this.toast.show('Erro', errorMessage(err, 'Nao foi possivel criar o motoboy.'), 'error')
    });
  }

  saveCourier(courier: Courier): void {
    const establishment = this.tenant.current();
    if (!establishment || courier.name.trim().length < 2) return;
    this.api.saveCourier(establishment.id, {
      id: courier.id,
      name: courier.name.trim(),
      phone: (courier.phone ?? '').trim() || null,
      fee_per_delivery: Number(courier.fee_per_delivery) || 0,
      active: courier.active
    }).subscribe({ error: (err) => this.toast.show('Erro', errorMessage(err, 'Nao foi possivel salvar o motoboy.'), 'error') });
  }

  deleteCourier(courier: Courier): void {
    const establishment = this.tenant.current();
    if (!establishment || !window.confirm(`Excluir o motoboy ${courier.name}?`)) return;
    this.api.deleteCourier(establishment.id, courier.id).subscribe({ next: () => this.couriers.update((items) => items.filter((item) => item.id !== courier.id)) });
  }

  saveSettings(): void {
    const establishment = this.tenant.current();
    if (!establishment) return;
    const commissions: Partial<Record<SalesChannel, number>> = {};
    for (const channel of CHANNELS) {
      const value = this.commissions[channel.id];
      if (value !== null && value !== undefined && (value as unknown) !== '') commissions[channel.id] = Number(value);
    }
    this.saving.set(true);
    this.api.updateEstablishment(establishment.id, {
      loyalty_enabled: this.loyalty.enabled,
      loyalty_goal: Math.max(1, Number(this.loyalty.goal) || 1),
      loyalty_reward: Number(this.loyalty.reward) || 0,
      channel_commissions: commissions
    }).subscribe({
      next: () => {
        this.saving.set(false);
        this.toast.show('Configuracoes salvas', 'Fidelidade e comissoes atualizadas.', 'success');
      },
      error: (err) => {
        this.saving.set(false);
        this.toast.show('Erro', errorMessage(err, 'Nao foi possivel salvar.'), 'error');
      }
    });
  }
}
