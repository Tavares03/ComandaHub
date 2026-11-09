import { Injectable, computed, effect, inject, signal } from '@angular/core';

import { AuthService } from './auth.service';
import { EstablishmentSummary, UserRole } from './models';

const ESTABLISHMENT_KEY = 'comandahub.establishment';

@Injectable({ providedIn: 'root' })
export class TenantService {
  private readonly auth = inject(AuthService);

  // Derivado do usuario logado (sincrono: os guards de rota ja enxergam a loja e o perfil)
  readonly establishments = computed<EstablishmentSummary[]>(() => this.auth.user()?.establishments ?? []);
  readonly currentId = signal<string | null>(localStorage.getItem(ESTABLISHMENT_KEY));
  readonly current = computed<EstablishmentSummary | null>(() => {
    const list = this.establishments();
    return list.find((item) => item.id === this.currentId()) ?? list[0] ?? null;
  });
  /** Perfil do usuario na loja selecionada */
  readonly role = computed<UserRole | null>(() => this.current()?.role ?? null);

  constructor() {
    // Loja salva que nao existe mais para este usuario: passa a usar a primeira da lista
    effect(() => {
      const list = this.establishments();
      const selected = this.currentId();
      if (list.length && (!selected || !list.some((item) => item.id === selected))) {
        this.select(list[0].id);
      }
    }, { allowSignalWrites: true });
  }

  select(id: string): void {
    localStorage.setItem(ESTABLISHMENT_KEY, id);
    this.currentId.set(id);
  }
}
