import { CanActivateFn, Router } from '@angular/router';
import { inject } from '@angular/core';

import { AuthService } from './auth.service';
import { canAccess, homeFor } from './roles';
import { TenantService } from './tenant.service';

export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  if (auth.token) {
    return true;
  }
  return router.createUrlTree(['/login']);
};

/** Tela fora do perfil (ex.: cozinha abrindo Relatorios) volta para a tela inicial do perfil. */
export const roleGuard: CanActivateFn = (route) => {
  const tenant = inject(TenantService);
  const router = inject(Router);
  const role = tenant.role();
  if (canAccess(route.routeConfig?.path ?? '', role)) {
    return true;
  }
  return router.parseUrl(homeFor(role));
};
