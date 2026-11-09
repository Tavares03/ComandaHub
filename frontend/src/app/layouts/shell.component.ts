import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, OnDestroy, OnInit, computed, effect, inject, signal, untracked } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';
import { LucideAngularModule } from 'lucide-angular';

import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import { ROLE_LABELS, canAccess, homeFor } from '../core/roles';
import { TenantService } from '../core/tenant.service';
import { ToastService, ToastMessage } from '../core/toast.service';
import { PasswordDialogComponent } from './password-dialog.component';

const PENDING_POLL_MS = 20000;

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive, RouterOutlet, LucideAngularModule, PasswordDialogComponent],
  template: `
    <div class="min-h-screen bg-[#f5f6f8] lg:flex">
      @if (sidebarOpen()) {
        <div class="fixed inset-0 z-40 bg-zinc-950/40 lg:hidden" (click)="sidebarOpen.set(false)"></div>
      }
      <!-- No computador: so icones (o nome aparece ao passar o mouse). No celular: menu com nomes pelo botao. -->
      <aside
        class="fixed inset-y-0 left-0 z-40 w-72 bg-graphite text-white transition-transform lg:sticky lg:top-0 lg:h-screen lg:w-16 lg:shrink-0 lg:translate-x-0"
        [class.-translate-x-full]="!sidebarOpen()"
      >
        <div class="flex h-16 items-center gap-3 border-b border-white/10 px-5 lg:justify-center lg:px-0">
          <div class="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-brand-500 text-white" title="ComandaHub">
            <i-lucide name="utensils" [size]="22" />
          </div>
          <div class="lg:hidden">
            <p class="text-lg font-extrabold tracking-normal">ComandaHub</p>
            <p class="text-xs text-white/50">Operacao unificada</p>
          </div>
          <button class="ml-auto rounded-md p-2 text-white/70 hover:bg-white/10 lg:hidden" (click)="sidebarOpen.set(false)" aria-label="Fechar menu">
            <i-lucide name="x" [size]="18" />
          </button>
        </div>

        <nav class="space-y-1 px-3 py-4 lg:px-2.5">
          @for (item of visibleNav(); track item.path) {
            <a
              [routerLink]="item.path"
              routerLinkActive="bg-white/10 text-white lg:bg-brand-500"
              class="group relative flex min-h-11 items-center gap-3 rounded-lg px-3 text-sm font-semibold text-white/70 transition hover:bg-white/10 hover:text-white lg:h-11 lg:w-11 lg:justify-center lg:px-0"
              [attr.aria-label]="item.label"
              (click)="sidebarOpen.set(false)"
            >
              <i-lucide [name]="item.icon" [size]="20" />
              <span class="lg:hidden">{{ item.label }}</span>
              <span
                class="pointer-events-none absolute left-full top-1/2 z-50 ml-3 hidden -translate-y-1/2 whitespace-nowrap rounded-md bg-zinc-900 px-2.5 py-1.5 text-xs font-bold text-white opacity-0 shadow-lg transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100 lg:block"
                aria-hidden="true"
              >
                {{ item.label }}
              </span>
            </a>
          }
        </nav>
      </aside>

      <div class="min-w-0 flex-1">
        <header class="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-zinc-200 bg-white/95 px-4 backdrop-blur lg:px-6">
          <button class="rounded-md border border-zinc-200 p-2 lg:hidden" (click)="sidebarOpen.set(true)" aria-label="Abrir menu">
            <i-lucide name="menu" [size]="20" />
          </button>

          <div class="min-w-0">
            <p class="truncate text-sm font-bold text-zinc-950">{{ tenant.current()?.name || 'ComandaHub' }}</p>
            <p class="text-xs text-zinc-500">{{ roleLabel() }}</p>
          </div>

          <div class="ml-auto flex items-center gap-3">
            <label class="hidden text-xs font-semibold text-zinc-500 md:block" for="tenant">Trocar loja</label>
            <select
              id="tenant"
              class="focus-ring h-10 max-w-40 rounded-md border border-zinc-200 bg-white px-3 text-sm font-semibold text-zinc-800 sm:max-w-none"
              [value]="tenant.current()?.id"
              (change)="selectTenant($event)"
            >
              @for (est of tenant.establishments(); track est.id) {
                <option [value]="est.id" [selected]="est.id === tenant.current()?.id">{{ est.name }}</option>
              }
            </select>
            @if (showBell()) {
              <a
                routerLink="/orders"
                class="focus-ring relative rounded-md border border-zinc-200 p-2 text-zinc-600 hover:bg-zinc-50"
                [attr.aria-label]="pendingLabel()"
                [title]="pendingLabel()"
              >
                <i-lucide name="bell" [size]="18" />
                @if (pending() > 0) {
                  <span class="absolute -right-1.5 -top-1.5 grid h-5 min-w-5 place-items-center rounded-full bg-brand-500 px-1 text-[11px] font-extrabold text-white">
                    {{ pending() > 99 ? '99+' : pending() }}
                  </span>
                }
              </a>
            }
            <button type="button" class="focus-ring hidden rounded-md px-2 py-1 text-right hover:bg-zinc-50 sm:block" (click)="passwordOpen.set(true)" title="Alterar minha senha">
              <p class="max-w-44 truncate text-sm font-semibold text-zinc-900">{{ auth.user()?.name }}</p>
              <p class="text-xs text-zinc-500">{{ auth.user()?.email }}</p>
            </button>
            <button class="focus-ring rounded-md border border-zinc-200 p-2 text-zinc-600 hover:bg-zinc-50" type="button" (click)="auth.logout()" aria-label="Sair" title="Sair">
              <i-lucide name="log-out" [size]="18" />
            </button>
          </div>
        </header>

        <main class="p-4 lg:p-6">
          <router-outlet />
        </main>
      </div>
    </div>

    @if (passwordOpen()) {
      <app-password-dialog (closed)="passwordOpen.set(false)" />
    }

    <div class="fixed right-4 top-20 z-50 w-[min(92vw,360px)] space-y-2">
      @for (toast of toasts.messages(); track toast.id) {
        <button
          class="w-full rounded-lg border bg-white p-4 text-left shadow-lg"
          [ngClass]="toastClass(toast)"
          (click)="toasts.dismiss(toast.id)"
        >
          <p class="text-sm font-bold">{{ toast.title }}</p>
          <p class="mt-1 text-sm text-zinc-600">{{ toast.message }}</p>
        </button>
      }
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class ShellComponent implements OnInit, OnDestroy {
  readonly auth = inject(AuthService);
  readonly tenant = inject(TenantService);
  readonly toasts = inject(ToastService);
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  readonly sidebarOpen = signal(false);
  readonly passwordOpen = signal(false);
  readonly pending = signal(0);
  private pendingTimer: number | null = null;

  readonly navItems = [
    { path: '/dashboard', label: 'Dashboard', icon: 'layout-dashboard' },
    { path: '/orders', label: 'Central de pedidos', icon: 'clipboard-list' },
    { path: '/local-order', label: 'Pedido local', icon: 'plus-circle' },
    { path: '/kitchen', label: 'Cozinha', icon: 'chef-hat' },
    { path: '/cash', label: 'Caixa', icon: 'wallet' },
    { path: '/customers', label: 'Clientes e cupons', icon: 'users' },
    { path: '/products', label: 'Cardapio', icon: 'shopping-bag' },
    { path: '/reports', label: 'Relatorios', icon: 'bar-chart-3' },
    { path: '/simulator', label: 'Laboratorio', icon: 'flask-conical' },
    { path: '/settings', label: 'Configuracoes', icon: 'settings' }
  ];
  readonly visibleNav = computed(() => this.navItems.filter((item) => canAccess(item.path, this.tenant.role())));
  readonly roleLabel = computed(() => {
    const role = this.tenant.role();
    return role ? `Perfil: ${ROLE_LABELS[role]}` : 'Painel operacional';
  });
  // O sino leva para a Central de pedidos: so para quem aceita pedidos
  readonly showBell = computed(() => canAccess('/orders', this.tenant.role()));
  readonly pendingLabel = computed(() => {
    const count = this.pending();
    if (!count) return 'Nenhum pedido novo aguardando';
    return count === 1 ? '1 pedido novo aguardando aceite' : `${count} pedidos novos aguardando aceite`;
  });

  constructor() {
    // Troca de loja: perfil pode mudar (ex.: admin em uma, cozinha em outra) e o contador e da loja
    effect(() => {
      const role = this.tenant.role();
      const establishment = this.tenant.current();
      untracked(() => {
        if (!canAccess(this.router.url, role)) {
          void this.router.navigateByUrl(homeFor(role));
        }
        this.pending.set(0);
        if (establishment && this.showBell()) this.loadPending();
      });
    }, { allowSignalWrites: true });
  }

  ngOnInit(): void {
    this.auth.loadMe().subscribe({ error: () => this.auth.logout() });
    this.pendingTimer = window.setInterval(() => this.loadPending(), PENDING_POLL_MS);
    // Ao sair da Central (onde os pedidos sao aceitos) o numero atualiza na hora
    this.router.events
      .pipe(filter((event) => event instanceof NavigationEnd), takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.loadPending());
  }

  ngOnDestroy(): void {
    if (this.pendingTimer !== null) window.clearInterval(this.pendingTimer);
  }

  loadPending(): void {
    const establishment = this.tenant.current();
    if (!establishment || !this.showBell() || document.hidden) return;
    this.api.pendingCount(establishment.id).subscribe({
      next: (result) => this.pending.set(result.new_orders),
      error: () => undefined
    });
  }

  selectTenant(event: Event): void {
    const id = (event.target as HTMLSelectElement).value;
    this.tenant.select(id);
  }

  toastClass(toast: ToastMessage): string {
    return {
      success: 'border-emerald-200',
      error: 'border-red-200',
      info: 'border-brand-200'
    }[toast.tone];
  }
}
