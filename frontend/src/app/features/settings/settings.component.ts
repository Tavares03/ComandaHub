import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, effect, inject, signal } from '@angular/core';
import { FormBuilder, FormsModule, ReactiveFormsModule, Validators } from '@angular/forms';
import { LucideAngularModule } from 'lucide-angular';

import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { Establishment, EstablishmentUser, UserRole } from '../../core/models';
import { ROLE_HINTS, ROLE_LABELS } from '../../core/roles';
import { OperationsSettingsComponent } from './operations-settings.component';
import { TenantService } from '../../core/tenant.service';
import { ToastService } from '../../core/toast.service';
import { errorMessage } from '../../shared/order-options';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [CommonModule, FormsModule, ReactiveFormsModule, LucideAngularModule, OperationsSettingsComponent],
  template: `
    <section class="grid gap-5 xl:grid-cols-[1fr_420px]">
      <div class="min-w-0 space-y-5">
        <div>
          <h1 class="text-2xl font-extrabold tracking-normal text-zinc-950">Configuracoes</h1>
          <p class="mt-1 text-sm text-zinc-500">Dados basicos do estabelecimento e status das integracoes.</p>
        </div>

        <form class="app-card p-5" [formGroup]="form" (ngSubmit)="save()">
          <div class="mb-5 flex items-center gap-2">
            <i-lucide class="text-brand-600" name="building-2" [size]="20" />
            <h2 class="text-lg font-extrabold text-zinc-950">Estabelecimento</h2>
          </div>
          <div class="grid gap-4 md:grid-cols-2">
            <label class="block">
              <span class="mb-1 block text-xs font-bold text-zinc-500">Nome fantasia</span>
              <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" formControlName="name" />
            </label>
            <label class="block">
              <span class="mb-1 block text-xs font-bold text-zinc-500">Razao social</span>
              <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" formControlName="legal_name" />
            </label>
            <label class="block">
              <span class="mb-1 block text-xs font-bold text-zinc-500">CNPJ</span>
              <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" formControlName="tax_id" />
            </label>
            <label class="block">
              <span class="mb-1 block text-xs font-bold text-zinc-500">Telefone</span>
              <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" formControlName="phone" />
            </label>
            <label class="block md:col-span-2">
              <span class="mb-1 block text-xs font-bold text-zinc-500">Endereco</span>
              <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" formControlName="address" />
            </label>
            <label class="block">
              <span class="mb-1 block text-xs font-bold text-zinc-500">Horario de funcionamento</span>
              <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" formControlName="opening_hours" />
            </label>
            <label class="block">
              <span class="mb-1 block text-xs font-bold text-zinc-500">Tempo medio de preparo</span>
              <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" type="number" formControlName="preparation_time" />
            </label>
            <label class="block md:col-span-2">
              <span class="mb-1 block text-xs font-bold text-zinc-500">Logo opcional</span>
              <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" formControlName="logo_url" />
            </label>
          </div>
          <button class="focus-ring mt-5 inline-flex h-10 items-center gap-2 rounded-lg bg-brand-500 px-4 text-sm font-extrabold text-white" type="submit" [disabled]="form.invalid || loading()">
            <i-lucide name="save" [size]="16" /> Salvar alteracoes
          </button>
        </form>

        <app-operations-settings class="block" />

        <article class="app-card p-5">
          <div class="mb-4 flex items-center gap-2">
            <i-lucide class="text-blue-600" name="plug-zap" [size]="20" />
            <h2 class="text-lg font-extrabold text-zinc-950">Integracoes</h2>
          </div>
          <div class="grid gap-3 md:grid-cols-3">
            @for (integration of integrations; track integration.name) {
              <div class="rounded-lg border border-zinc-200 p-4">
                <p class="font-extrabold text-zinc-950">{{ integration.name }}</p>
                <p class="mt-2 inline-flex items-center gap-1 rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-bold text-zinc-700">
                  <i-lucide name="check-circle-2" [size]="14" /> {{ integration.status }}
                </p>
              </div>
            }
          </div>
        </article>
      </div>

      <aside class="app-card h-max overflow-hidden">
        <div class="border-b border-zinc-100 p-5">
          <div class="flex items-center gap-2">
            <i-lucide class="text-emerald-600" name="users" [size]="20" />
            <h2 class="text-lg font-extrabold text-zinc-950">Usuarios da loja</h2>
          </div>
          <p class="mt-1 text-xs text-zinc-500">Quem acessa esta loja e o que cada um pode fazer.</p>
        </div>
        <div class="divide-y divide-zinc-100">
          @for (user of users(); track user.id) {
            <div class="p-4">
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <p class="truncate font-extrabold text-zinc-950">
                    {{ user.name }}
                    @if (isMe(user)) {
                      <span class="text-xs font-bold text-zinc-400">(voce)</span>
                    }
                  </p>
                  <p class="truncate text-sm text-zinc-500">{{ user.email }}</p>
                </div>
                @if (!isMe(user)) {
                  <button type="button" class="focus-ring shrink-0 rounded p-1.5 text-red-600 hover:bg-red-50" (click)="remove(user)" [attr.aria-label]="'Remover ' + user.name" title="Remover acesso a esta loja">
                    <i-lucide name="trash-2" [size]="15" />
                  </button>
                }
              </div>
              <div class="mt-2 flex flex-wrap items-center gap-2">
                <select class="focus-ring h-9 rounded-md border border-zinc-200 bg-white px-2 text-xs font-bold text-zinc-700 disabled:bg-zinc-50"
                        [ngModel]="user.role" (ngModelChange)="changeRole(user, $event)" [disabled]="isMe(user)" [attr.aria-label]="'Perfil de ' + user.name">
                  @for (role of roles; track role) {
                    <option [value]="role">{{ roleLabels[role] }}</option>
                  }
                </select>
                @if (!isMe(user)) {
                  <button type="button" class="focus-ring h-9 rounded-md border border-zinc-200 px-2.5 text-xs font-bold text-zinc-700 hover:bg-zinc-50" (click)="toggleReset(user)">
                    Redefinir senha
                  </button>
                }
              </div>
              @if (resetting() === user.id) {
                <form class="mt-2 flex gap-2" (ngSubmit)="resetPassword(user)">
                  <input class="focus-ring h-9 min-w-0 flex-1 rounded-md border border-zinc-200 px-2 text-sm" type="password" name="reset" autocomplete="new-password"
                         placeholder="Nova senha (6+ caracteres)" [(ngModel)]="resetValue" />
                  <button class="focus-ring h-9 rounded-md bg-zinc-900 px-3 text-xs font-bold text-white disabled:opacity-50" type="submit" [disabled]="resetValue.length < 6">Salvar</button>
                </form>
              }
            </div>
          } @empty {
            <p class="p-5 text-sm text-zinc-500">Nenhum usuario encontrado.</p>
          }
        </div>
        <form class="space-y-2 border-t border-zinc-100 bg-zinc-50/60 p-5" (ngSubmit)="addUser()">
          <p class="text-sm font-extrabold text-zinc-950">Adicionar usuario</p>
          <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" name="newName" placeholder="Nome" [(ngModel)]="newUser.name" />
          <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" name="newEmail" type="email" placeholder="E-mail" autocomplete="off" [(ngModel)]="newUser.email" />
          <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" name="newPassword" type="password" placeholder="Senha inicial (6+ caracteres)" autocomplete="new-password" [(ngModel)]="newUser.password" />
          <select class="focus-ring h-10 w-full rounded-lg border border-zinc-200 bg-white px-2 text-sm" name="newRole" [(ngModel)]="newUser.role">
            @for (role of roles; track role) {
              <option [value]="role">{{ roleLabels[role] }} - {{ roleHints[role] }}</option>
            }
          </select>
          <p class="text-xs text-zinc-500">Se o e-mail ja usa o ComandaHub em outra loja, ele so ganha acesso a esta e continua com a senha dele.</p>
          <button class="focus-ring inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-brand-500 text-sm font-extrabold text-white hover:bg-brand-600 disabled:opacity-50"
                  type="submit" [disabled]="!canAdd() || savingUser()">
            <i-lucide name="plus" [size]="16" /> Adicionar
          </button>
        </form>
      </aside>
    </section>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class SettingsComponent {
  private readonly api = inject(ApiService);
  private readonly auth = inject(AuthService);
  private readonly tenant = inject(TenantService);
  private readonly toast = inject(ToastService);
  private readonly fb = inject(FormBuilder);

  readonly users = signal<EstablishmentUser[]>([]);
  readonly loading = signal(false);
  readonly savingUser = signal(false);
  readonly resetting = signal<string | null>(null);
  readonly roles: UserRole[] = ['ADMIN', 'ATTENDANT', 'KITCHEN'];
  readonly roleLabels = ROLE_LABELS;
  readonly roleHints = ROLE_HINTS;
  newUser = { name: '', email: '', password: '', role: 'ATTENDANT' as UserRole };
  resetValue = '';
  readonly form = this.fb.nonNullable.group({
    name: ['', Validators.required],
    legal_name: [''],
    tax_id: [''],
    phone: [''],
    address: [''],
    opening_hours: [''],
    logo_url: [''],
    preparation_time: [18, [Validators.required, Validators.min(1)]]
  });

  readonly integrations = [
    { name: 'iFood', status: 'Modo demonstracao' },
    { name: '99Food', status: 'Modo demonstracao' },
    { name: 'Delivery proprio', status: 'Disponivel' }
  ];

  constructor() {
    effect(() => {
      const establishment = this.tenant.current();
      if (establishment) this.load(establishment.id);
    }, { allowSignalWrites: true });
  }

  load(establishmentId: string): void {
    this.api.establishment(establishmentId).subscribe({
      next: (establishment) => this.patchForm(establishment)
    });
    this.api.establishmentUsers(establishmentId).subscribe({
      next: (users) => this.users.set(users)
    });
  }

  patchForm(establishment: Establishment): void {
    this.form.patchValue({
      name: establishment.name,
      legal_name: establishment.legal_name ?? '',
      tax_id: establishment.tax_id ?? '',
      phone: establishment.phone ?? '',
      address: establishment.address ?? '',
      opening_hours: establishment.opening_hours ?? '',
      logo_url: establishment.logo_url ?? '',
      preparation_time: establishment.preparation_time
    });
  }

  isMe(user: EstablishmentUser): boolean {
    return user.id === this.auth.user()?.id;
  }

  canAdd(): boolean {
    return this.newUser.name.trim().length >= 2 && /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(this.newUser.email.trim()) && this.newUser.password.length >= 6;
  }

  addUser(): void {
    const establishment = this.tenant.current();
    if (!establishment || !this.canAdd()) return;
    this.savingUser.set(true);
    this.api.addEstablishmentUser(establishment.id, { ...this.newUser, name: this.newUser.name.trim(), email: this.newUser.email.trim() }).subscribe({
      next: (user) => {
        this.savingUser.set(false);
        this.users.update((items) => [...items, user].sort((a, b) => a.name.localeCompare(b.name)));
        this.newUser = { name: '', email: '', password: '', role: 'ATTENDANT' };
        this.toast.show('Usuario adicionado', `${user.name} ja pode entrar com o e-mail ${user.email}.`, 'success');
      },
      error: (err) => {
        this.savingUser.set(false);
        this.toast.show('Erro', errorMessage(err, 'Nao foi possivel adicionar o usuario.'), 'error');
      }
    });
  }

  changeRole(user: EstablishmentUser, role: UserRole): void {
    const establishment = this.tenant.current();
    if (!establishment || role === user.role) return;
    this.api.updateEstablishmentUser(establishment.id, user.id, { role }).subscribe({
      next: (updated) => {
        this.users.update((items) => items.map((item) => (item.id === updated.id ? updated : item)));
        this.toast.show('Perfil alterado', `${updated.name} agora e ${ROLE_LABELS[updated.role]}.`, 'success');
      },
      error: (err) => {
        this.users.set([...this.users()]);
        this.toast.show('Erro', errorMessage(err, 'Nao foi possivel alterar o perfil.'), 'error');
      }
    });
  }

  toggleReset(user: EstablishmentUser): void {
    this.resetValue = '';
    this.resetting.set(this.resetting() === user.id ? null : user.id);
  }

  resetPassword(user: EstablishmentUser): void {
    const establishment = this.tenant.current();
    if (!establishment || this.resetValue.length < 6) return;
    this.api.updateEstablishmentUser(establishment.id, user.id, { password: this.resetValue }).subscribe({
      next: () => {
        this.resetting.set(null);
        this.resetValue = '';
        this.toast.show('Senha redefinida', `Passe a nova senha para ${user.name}.`, 'success');
      },
      error: (err) => this.toast.show('Erro', errorMessage(err, 'Nao foi possivel redefinir a senha.'), 'error')
    });
  }

  remove(user: EstablishmentUser): void {
    const establishment = this.tenant.current();
    if (!establishment || !window.confirm(`Remover o acesso de ${user.name} a ${establishment.name}?`)) return;
    this.api.removeEstablishmentUser(establishment.id, user.id).subscribe({
      next: () => {
        this.users.update((items) => items.filter((item) => item.id !== user.id));
        this.toast.show('Acesso removido', `${user.name} nao acessa mais esta loja.`, 'success');
      },
      error: (err) => this.toast.show('Erro', errorMessage(err, 'Nao foi possivel remover.'), 'error')
    });
  }

  save(): void {
    const establishment = this.tenant.current();
    if (!establishment || this.form.invalid) return;
    this.loading.set(true);
    this.api.updateEstablishment(establishment.id, this.form.getRawValue()).subscribe({
      next: () => this.toast.show('Configuracoes salvas', 'Dados do estabelecimento atualizados.', 'success'),
      error: (err) => this.toast.show('Erro ao salvar', err?.error?.detail ?? 'Verifique sua permissao.', 'error'),
      complete: () => this.loading.set(false)
    });
  }
}
