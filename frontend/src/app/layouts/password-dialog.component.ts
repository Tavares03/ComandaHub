import { ChangeDetectionStrategy, Component, EventEmitter, Output, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { LucideAngularModule } from 'lucide-angular';

import { AuthService } from '../core/auth.service';
import { ToastService } from '../core/toast.service';
import { errorMessage } from '../shared/order-options';

/** Troca da propria senha (qualquer perfil). */
@Component({
  selector: 'app-password-dialog',
  standalone: true,
  imports: [FormsModule, LucideAngularModule],
  template: `
    <div class="fixed inset-0 z-50 bg-zinc-950/40" (click)="closed.emit()"></div>
    <form class="fixed left-1/2 top-24 z-50 w-[min(92vw,400px)] -translate-x-1/2 rounded-xl bg-white p-5 shadow-2xl"
          role="dialog" aria-modal="true" aria-label="Alterar minha senha" (ngSubmit)="save()">
      <div class="mb-4 flex items-center justify-between">
        <h2 class="text-lg font-extrabold text-zinc-950">Alterar minha senha</h2>
        <button type="button" class="focus-ring rounded-md p-1.5 text-zinc-500 hover:bg-zinc-100" (click)="closed.emit()" aria-label="Fechar">
          <i-lucide name="x" [size]="18" />
        </button>
      </div>
      <label class="mb-3 block">
        <span class="mb-1 block text-xs font-bold text-zinc-500">Senha atual</span>
        <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" type="password" name="current" autocomplete="current-password" [(ngModel)]="current" />
      </label>
      <label class="mb-3 block">
        <span class="mb-1 block text-xs font-bold text-zinc-500">Nova senha (minimo 6 caracteres)</span>
        <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" type="password" name="next" autocomplete="new-password" [(ngModel)]="next" />
      </label>
      <label class="mb-4 block">
        <span class="mb-1 block text-xs font-bold text-zinc-500">Repita a nova senha</span>
        <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" type="password" name="confirm" autocomplete="new-password" [(ngModel)]="confirm" />
      </label>
      @if (problem(); as message) {
        <p class="mb-3 text-xs font-bold text-red-600">{{ message }}</p>
      }
      <button class="focus-ring inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-brand-500 text-sm font-extrabold text-white hover:bg-brand-600 disabled:opacity-50"
              type="submit" [disabled]="saving()">
        <i-lucide name="save" [size]="16" /> Salvar nova senha
      </button>
    </form>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class PasswordDialogComponent {
  @Output() readonly closed = new EventEmitter<void>();

  private readonly auth = inject(AuthService);
  private readonly toast = inject(ToastService);

  readonly saving = signal(false);
  readonly problem = signal<string | null>(null);
  current = '';
  next = '';
  confirm = '';

  save(): void {
    if (!this.current) return this.problem.set('Informe a senha atual.');
    if (this.next.length < 6) return this.problem.set('A nova senha precisa de pelo menos 6 caracteres.');
    if (this.next !== this.confirm) return this.problem.set('As senhas novas nao conferem.');
    this.problem.set(null);
    this.saving.set(true);
    this.auth.changePassword(this.current, this.next).subscribe({
      next: () => {
        this.saving.set(false);
        this.toast.show('Senha alterada', 'Use a nova senha no proximo login.', 'success');
        this.closed.emit();
      },
      error: (err) => {
        this.saving.set(false);
        this.problem.set(errorMessage(err, 'Nao foi possivel alterar a senha.'));
      }
    });
  }
}
