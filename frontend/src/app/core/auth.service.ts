import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, tap } from 'rxjs';

import { ApiService } from './api.service';
import { AuthUser, LoginResponse } from './models';
import { TOKEN_KEY } from './http.interceptor';

const USER_KEY = 'comandahub.user';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);

  readonly user = signal<AuthUser | null>(this.readStoredUser());
  readonly isAuthenticated = computed(() => Boolean(this.token));

  get token(): string | null {
    return localStorage.getItem(TOKEN_KEY);
  }

  login(email: string, password: string): Observable<LoginResponse> {
    return this.api.login(email, password).pipe(
      tap((response) => {
        localStorage.setItem(TOKEN_KEY, response.access_token);
        localStorage.setItem(USER_KEY, JSON.stringify(response.user));
        this.user.set(response.user);
      })
    );
  }

  loadMe(): Observable<AuthUser> {
    return this.api.me().pipe(
      tap((user) => {
        localStorage.setItem(USER_KEY, JSON.stringify(user));
        this.user.set(user);
      })
    );
  }

  changePassword(currentPassword: string, newPassword: string): Observable<void> {
    return this.api.changeMyPassword(currentPassword, newPassword);
  }

  /** expired = sessao venceu (a tela de login avisa o motivo) */
  logout(expired = false): void {
    const wasLoggedIn = Boolean(this.token);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    this.user.set(null);
    // Varias requisicoes podem voltar 401 juntas (polling): so a primeira redireciona
    if (expired && !wasLoggedIn) return;
    void this.router.navigate(['/login'], expired ? { queryParams: { sessao: 'expirada' } } : {});
  }

  private readStoredUser(): AuthUser | null {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) {
      return null;
    }
    try {
      return JSON.parse(raw) as AuthUser;
    } catch {
      localStorage.removeItem(USER_KEY);
      return null;
    }
  }
}
