import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, effect, inject, signal, untracked } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { LucideAngularModule } from 'lucide-angular';

import { ApiService } from '../../core/api.service';
import { IfoodIntegration } from '../../core/models';
import { TenantService } from '../../core/tenant.service';
import { ToastService } from '../../core/toast.service';
import { errorMessage } from '../../shared/order-options';

/** iFood real (liga a loja pelo ID do iFood) e o status dos outros canais. */
@Component({
  selector: 'app-integrations-settings',
  standalone: true,
  imports: [CommonModule, FormsModule, LucideAngularModule],
  template: `
    <article class="app-card p-5">
      <div class="mb-4 flex items-center gap-2">
        <i-lucide class="text-blue-600" name="plug-zap" [size]="20" />
        <h2 class="text-lg font-extrabold text-zinc-950">Integracoes</h2>
      </div>

      <div class="rounded-lg border border-zinc-200 p-4">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <p class="font-extrabold text-zinc-950">iFood</p>
          @if (ifood(); as state) {
            @if (!state.configured) {
              <span class="rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-bold text-zinc-600">Nao configurado</span>
            } @else if (state.merchant_id && state.store_status) {
              <span class="rounded-full px-2.5 py-1 text-xs font-bold" [ngClass]="state.store_status.available ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'">
                {{ state.store_status.title }}
              </span>
            } @else if (state.merchant_id) {
              <span class="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-bold text-amber-800">Verificar</span>
            } @else {
              <span class="rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-bold text-zinc-600">Desconectado</span>
            }
          }
        </div>

        @if (ifood(); as state) {
          @if (!state.configured) {
            <p class="mt-2 text-sm text-zinc-600">
              Para receber pedidos reais, crie um app <strong>centralizado</strong> no Portal do Desenvolvedor do iFood e defina
              <code class="rounded bg-zinc-100 px-1">IFOOD_CLIENT_ID</code> e <code class="rounded bg-zinc-100 px-1">IFOOD_CLIENT_SECRET</code> no servidor.
              Enquanto isso, use o Laboratorio para simular pedidos.
            </p>
          } @else {
            @if (state.merchant_id) {
              <p class="mt-2 text-sm text-zinc-700">
                Ligada a <strong>{{ state.merchant_name || state.merchant_id }}</strong>.
                {{ state.store_status?.subtitle || '' }}
              </p>
              <p class="mt-1 text-xs text-zinc-500">
                {{ state.polling ? 'Pedidos chegam sozinhos na Central (verificacao a cada 30 s, que tambem mantem a loja aberta no iFood).' : 'Polling desligado neste servidor (IFOOD_POLLING_ENABLED=false): os pedidos nao serao recebidos.' }}
              </p>
            } @else {
              <p class="mt-2 text-sm text-zinc-600">Informe o ID da loja no iFood (merchant ID). Ele aparece no Portal do Parceiro e, no ambiente de teste, no Portal do Desenvolvedor.</p>
            }
            @if (state.error) {
              <p class="mt-2 rounded-md bg-red-50 px-3 py-2 text-xs font-bold text-red-700">{{ state.error }}</p>
            }
            <form class="mt-3 flex flex-wrap gap-2" (ngSubmit)="link()">
              <input class="focus-ring h-10 min-w-0 flex-1 rounded-lg border border-zinc-200 px-3 font-mono text-sm" name="merchantId"
                     placeholder="ex.: e9a57b82-b56d-40db-9ec3-1077954a473e" [(ngModel)]="merchantId" autocomplete="off" />
              <button class="focus-ring inline-flex h-10 items-center gap-2 rounded-lg bg-red-600 px-4 text-sm font-extrabold text-white hover:bg-red-700 disabled:opacity-50"
                      type="submit" [disabled]="saving() || !merchantId.trim() || merchantId.trim() === state.merchant_id">
                {{ state.merchant_id ? 'Trocar loja' : 'Conectar' }}
              </button>
              @if (state.merchant_id) {
                <button class="focus-ring h-10 rounded-lg border border-zinc-200 px-4 text-sm font-bold text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
                        type="button" [disabled]="saving()" (click)="unlink()">Desconectar</button>
              }
            </form>
          }
        } @else {
          <p class="mt-2 text-sm text-zinc-500">Carregando...</p>
        }
      </div>

      <div class="mt-3 grid gap-3 md:grid-cols-2">
        <div class="rounded-lg border border-zinc-200 p-4">
          <p class="font-extrabold text-zinc-950">99Food</p>
          <p class="mt-1 text-xs text-zinc-500">Integracao real em breve. Hoje: pedidos simulados pelo Laboratorio.</p>
        </div>
        <div class="rounded-lg border border-zinc-200 p-4">
          <p class="font-extrabold text-zinc-950">Delivery proprio e cardapio online</p>
          <p class="mt-1 text-xs text-zinc-500">Ativo. Configure o link e os bairros abaixo.</p>
        </div>
      </div>
    </article>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class IntegrationsSettingsComponent {
  private readonly api = inject(ApiService);
  private readonly tenant = inject(TenantService);
  private readonly toast = inject(ToastService);

  readonly ifood = signal<IfoodIntegration | null>(null);
  readonly saving = signal(false);
  merchantId = '';

  constructor() {
    effect(() => {
      const establishment = this.tenant.current();
      if (establishment) untracked(() => this.load(establishment.id));
    }, { allowSignalWrites: true });
  }

  load(establishmentId: string): void {
    this.ifood.set(null);
    this.api.ifoodIntegration(establishmentId).subscribe({
      next: (state) => {
        this.ifood.set(state);
        this.merchantId = state.merchant_id ?? '';
      },
      error: () => this.ifood.set({ configured: false, polling: false, error: 'Nao foi possivel consultar a integracao.' })
    });
  }

  link(): void {
    this.save(this.merchantId.trim() || null, 'iFood conectado', 'Os pedidos desta loja do iFood vao cair na Central.');
  }

  unlink(): void {
    if (!window.confirm('Desconectar esta loja do iFood? Os pedidos do iFood deixam de chegar aqui.')) return;
    this.save(null, 'iFood desconectado', 'Os pedidos do iFood nao chegam mais nesta loja.');
  }

  private save(merchantId: string | null, title: string, message: string): void {
    const establishment = this.tenant.current();
    if (!establishment) return;
    this.saving.set(true);
    this.api.linkIfood(establishment.id, merchantId).subscribe({
      next: (state) => {
        this.saving.set(false);
        this.ifood.set(state);
        this.merchantId = state.merchant_id ?? '';
        this.toast.show(title, message, 'success');
      },
      error: (err) => {
        this.saving.set(false);
        this.toast.show('Erro', errorMessage(err, 'Nao foi possivel salvar a integracao.'), 'error');
      }
    });
  }
}
