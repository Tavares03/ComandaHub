import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { LoaderCircle, Lock, Mail, Store, Utensils, LucideAngularModule } from 'lucide-angular';

import { environment } from '../../../environments/environment';
import { AuthService } from '../../core/auth.service';
import { homeFor } from '../../core/roles';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, LucideAngularModule],
  template: `
    <section
      class="grid min-h-screen bg-zinc-950 lg:grid-cols-[1.08fr_0.92fr]"
      style="background-image: linear-gradient(120deg, rgba(17, 24, 39, 0.92), rgba(124, 45, 18, 0.62)), url('https://images.unsplash.com/photo-1550547660-d9450f859349?auto=format&fit=crop&w=1800&q=80'); background-size: cover; background-position: center;"
    >
      <div class="flex min-h-[42vh] items-end p-8 text-white lg:min-h-screen lg:p-12">
        <div class="max-w-2xl">
          <div class="mb-6 inline-flex items-center gap-3 rounded-lg bg-white/10 px-4 py-3 backdrop-blur">
            <span class="grid h-10 w-10 place-items-center rounded-md bg-brand-500">
              <i-lucide name="utensils" [size]="22" />
            </span>
            <span class="text-xl font-extrabold">ComandaHub</span>
          </div>
          <h1 class="max-w-xl text-4xl font-extrabold leading-tight tracking-normal md:text-6xl">Pedidos de todos os canais em uma operacao clara.</h1>
          <p class="mt-5 max-w-xl text-base leading-7 text-white/75">
            iFood, 99Food, delivery proprio, retirada e balcao na mesma central: cozinha, caixa, estoque, clientes e relatorios.
          </p>
        </div>
      </div>

      <div class="flex items-center justify-center bg-white px-5 py-10 lg:bg-white/95">
        <form class="w-full max-w-md" [formGroup]="form" (ngSubmit)="submit()">
          <div class="mb-8">
            @if (demoMode) {
              <p class="inline-flex items-center gap-2 rounded-full bg-brand-50 px-3 py-1 text-xs font-bold uppercase text-brand-700">
                <i-lucide name="store" [size]="14" /> Ambiente demo
              </p>
            }
            <h2 class="mt-4 text-3xl font-extrabold tracking-normal text-zinc-950">Entrar no painel</h2>
            <p class="mt-2 text-sm text-zinc-500">{{ demoMode ? 'Use as credenciais ficticias para testar o fluxo completo.' : 'Acesse com o e-mail e a senha da sua loja.' }}</p>
          </div>

          @if (sessionExpired()) {
            <div class="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-800">Sua sessao expirou. Entre de novo para continuar.</div>
          }

          <label class="mb-4 block">
            <span class="mb-2 block text-sm font-semibold text-zinc-700">E-mail</span>
            <span class="relative block">
              <i-lucide class="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" name="mail" [size]="18" />
              <input
                class="focus-ring h-12 w-full rounded-lg border border-zinc-200 bg-white pl-10 pr-3 text-sm"
                type="email"
                formControlName="email"
                autocomplete="email"
              />
            </span>
          </label>

          <label class="mb-5 block">
            <span class="mb-2 block text-sm font-semibold text-zinc-700">Senha</span>
            <span class="relative block">
              <i-lucide class="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" name="lock" [size]="18" />
              <input
                class="focus-ring h-12 w-full rounded-lg border border-zinc-200 bg-white pl-10 pr-3 text-sm"
                type="password"
                formControlName="password"
                autocomplete="current-password"
              />
            </span>
          </label>

          @if (error()) {
            <div class="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700">{{ error() }}</div>
          }

          <button
            class="focus-ring flex h-12 w-full items-center justify-center gap-2 rounded-lg bg-brand-500 px-4 text-sm font-bold text-white transition hover:bg-brand-600"
            type="submit"
            [disabled]="form.invalid || loading()"
          >
            @if (loading()) {
              <i-lucide class="animate-spin" name="loader-circle" [size]="18" />
            }
            Entrar
          </button>

          @if (demoMode) {
            <div class="mt-6 rounded-lg border border-zinc-200 bg-zinc-50 p-4 text-sm text-zinc-600">
              <p class="font-bold text-zinc-900">Credenciais demo (senha demo123)</p>
              @for (account of demoAccounts; track account.email) {
                <button type="button" class="mt-1 block w-full rounded px-1 text-left hover:bg-zinc-100" (click)="useDemo(account.email)">
                  <span class="font-semibold text-zinc-800">{{ account.email }}</span> <span class="text-zinc-500">- {{ account.label }}</span>
                </button>
              }
            </div>
          }
        </form>
      </div>
    </section>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class LoginComponent {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  readonly demoMode = environment.demoMode;
  readonly demoAccounts = [
    { email: 'admin@comandahub.local', label: 'administrador das 3 lojas' },
    { email: 'burger@comandahub.local', label: 'atendente do Burger Station' },
    { email: 'pizza@comandahub.local', label: 'atendente da Pizzaria' },
    { email: 'cozinha@comandahub.local', label: 'cozinha das 3 lojas' }
  ];
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly sessionExpired = signal(this.route.snapshot.queryParamMap.get('sessao') === 'expirada');
  readonly form = this.fb.nonNullable.group({
    email: [this.demoMode ? 'admin@comandahub.local' : '', [Validators.required]],
    password: [this.demoMode ? 'demo123' : '', [Validators.required]]
  });

  useDemo(email: string): void {
    this.form.setValue({ email, password: 'demo123' });
  }

  submit(): void {
    if (this.form.invalid || this.loading()) {
      return;
    }
    this.loading.set(true);
    this.error.set(null);
    const { email, password } = this.form.getRawValue();
    this.auth.login(email, password).subscribe({
      next: (response) => void this.router.navigateByUrl(homeFor(response.user.establishments[0]?.role)),
      error: (err) => {
        this.error.set(err?.error?.detail ?? 'Nao foi possivel entrar. Confira os dados.');
        this.loading.set(false);
      },
      complete: () => this.loading.set(false)
    });
  }
}
