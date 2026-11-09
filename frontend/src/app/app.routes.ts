import { Routes } from '@angular/router';

import { authGuard, roleGuard } from './core/auth.guard';
import { ShellComponent } from './layouts/shell.component';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () => import('./features/auth/login.component').then((m) => m.LoginComponent)
  },
  // Publico (cliente final, sem login): cardapio online e acompanhamento do pedido
  {
    path: 'cardapio/:slug',
    loadComponent: () => import('./features/public-menu/public-menu.component').then((m) => m.PublicMenuComponent)
  },
  {
    path: 'pedido/:token',
    loadComponent: () => import('./features/public-menu/order-tracking.component').then((m) => m.OrderTrackingComponent)
  },
  {
    path: '',
    component: ShellComponent,
    canActivate: [authGuard],
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
      { path: 'dashboard', canActivate: [roleGuard], loadComponent: () => import('./features/dashboard/dashboard.component').then((m) => m.DashboardComponent) },
      { path: 'orders', canActivate: [roleGuard], loadComponent: () => import('./features/orders/orders.component').then((m) => m.OrdersComponent) },
      { path: 'local-order', canActivate: [roleGuard], loadComponent: () => import('./features/local-order/local-order.component').then((m) => m.LocalOrderComponent) },
      { path: 'customers', canActivate: [roleGuard], loadComponent: () => import('./features/customers/customers.component').then((m) => m.CustomersComponent) },
      { path: 'cash', canActivate: [roleGuard], loadComponent: () => import('./features/cash/cash.component').then((m) => m.CashComponent) },
      { path: 'kitchen', canActivate: [roleGuard], loadComponent: () => import('./features/kitchen/kitchen.component').then((m) => m.KitchenComponent) },
      { path: 'products', canActivate: [roleGuard], loadComponent: () => import('./features/products/products.component').then((m) => m.ProductsComponent) },
      { path: 'reports', canActivate: [roleGuard], loadComponent: () => import('./features/reports/reports.component').then((m) => m.ReportsComponent) },
      { path: 'simulator', canActivate: [roleGuard], loadComponent: () => import('./features/simulator/simulator.component').then((m) => m.SimulatorComponent) },
      { path: 'settings', canActivate: [roleGuard], loadComponent: () => import('./features/settings/settings.component').then((m) => m.SettingsComponent) }
    ]
  },
  { path: '**', redirectTo: 'dashboard' }
];
