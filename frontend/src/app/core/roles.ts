import { environment } from '../../environments/environment';
import { UserRole } from './models';

export const ROLE_LABELS: Record<UserRole, string> = {
  ADMIN: 'Administrador',
  ATTENDANT: 'Atendente',
  KITCHEN: 'Cozinha'
};

export const ROLE_HINTS: Record<UserRole, string> = {
  ADMIN: 'Tudo, incluindo relatorios, usuarios e configuracoes',
  ATTENDANT: 'Pedidos, caixa, clientes e cardapio',
  KITCHEN: 'Tela da cozinha e estoque'
};

const STAFF: UserRole[] = ['ADMIN', 'ATTENDANT'];
const EVERYONE: UserRole[] = ['ADMIN', 'ATTENDANT', 'KITCHEN'];

/** Quem ve cada tela (o backend aplica as mesmas regras nos endpoints). */
const ROUTE_ROLES: Record<string, UserRole[]> = {
  dashboard: STAFF,
  orders: STAFF,
  'local-order': STAFF,
  kitchen: EVERYONE,
  cash: STAFF,
  customers: STAFF,
  products: EVERYONE,
  reports: ['ADMIN'],
  simulator: STAFF,
  settings: ['ADMIN']
};

export function canAccess(path: string, role: UserRole | null | undefined): boolean {
  const key = path.replace(/^\//, '').split(/[/?#]/)[0];
  // Laboratorio de pedidos simulados so existe no modo demo (o backend tambem o desliga em producao)
  if (key === 'simulator' && !environment.demoMode) return false;
  const allowed = ROUTE_ROLES[key];
  return !allowed || !role || allowed.includes(role);
}

/** Primeira tela do perfil */
export function homeFor(role: UserRole | null | undefined): string {
  return role === 'KITCHEN' ? '/kitchen' : '/dashboard';
}
