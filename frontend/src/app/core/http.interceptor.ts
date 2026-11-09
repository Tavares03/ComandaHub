import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';

import { AuthService } from './auth.service';

export const TOKEN_KEY = 'comandahub.token';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (!token) {
    return next(req);
  }
  const auth = inject(AuthService);
  return next(req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })).pipe(
    catchError((error: unknown) => {
      // Token vencido/invalido com a tela aberta (ex.: Central de pedidos no fim do turno):
      // sem isso o polling falhava em silencio e pedidos novos paravam de aparecer.
      if (error instanceof HttpErrorResponse && error.status === 401 && !req.url.endsWith('/auth/login')) {
        auth.logout(true);
      }
      return throwError(() => error);
    })
  );
};
