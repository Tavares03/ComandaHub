import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import {
  AuthUser,
  AvailabilityRequest,
  AvailabilityResponse,
  CancellationReason,
  CashSummary,
  Category,
  Coupon,
  CouponInput,
  Courier,
  CourierReportRow,
  Customer,
  DeliveryZone,
  DashboardResponse,
  Establishment,
  EstablishmentSummary,
  EstablishmentUser,
  IfoodIntegration,
  Ingredient,
  IngredientInput,
  LoginResponse,
  Order,
  OrderListResponse,
  OrderSource,
  OrderStatus,
  PaymentStatus,
  Product,
  ProfitByChannel,
  PublicOrderStatus,
  PublicStore,
  ProductInput,
  ReportOverview,
  SalesChannel,
  StockMovement,
  UserRole
} from './models';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = environment.apiUrl;

  login(email: string, password: string): Observable<LoginResponse> {
    return this.http.post<LoginResponse>(`${this.baseUrl}/auth/login`, { email, password });
  }

  me(): Observable<AuthUser> {
    return this.http.get<AuthUser>(`${this.baseUrl}/auth/me`);
  }

  changeMyPassword(currentPassword: string, newPassword: string): Observable<void> {
    return this.http.post<void>(`${this.baseUrl}/auth/me/password`, { current_password: currentPassword, new_password: newPassword });
  }

  establishments(): Observable<Establishment[]> {
    return this.http.get<Establishment[]>(`${this.baseUrl}/establishments`);
  }

  establishment(id: string): Observable<Establishment> {
    return this.http.get<Establishment>(`${this.baseUrl}/establishments/${id}`);
  }

  updateEstablishment(id: string, payload: Partial<Establishment>): Observable<Establishment> {
    return this.http.patch<Establishment>(`${this.baseUrl}/establishments/${id}`, payload);
  }

  establishmentUsers(id: string): Observable<EstablishmentUser[]> {
    return this.http.get<EstablishmentUser[]>(`${this.baseUrl}/establishments/${id}/users`);
  }

  /** Cria o usuario ou, se o e-mail ja existe em outra loja, so da acesso a esta */
  addEstablishmentUser(id: string, payload: { name: string; email: string; password: string; role: UserRole }): Observable<EstablishmentUser> {
    return this.http.post<EstablishmentUser>(`${this.baseUrl}/establishments/${id}/users`, payload);
  }

  updateEstablishmentUser(id: string, userId: string, payload: { role?: UserRole; name?: string; password?: string }): Observable<EstablishmentUser> {
    return this.http.patch<EstablishmentUser>(`${this.baseUrl}/establishments/${id}/users/${userId}`, payload);
  }

  removeEstablishmentUser(id: string, userId: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/establishments/${id}/users/${userId}`);
  }

  dashboard(establishmentId: string): Observable<DashboardResponse> {
    return this.http.get<DashboardResponse>(`${this.baseUrl}/establishments/${establishmentId}/dashboard`);
  }

  orders(establishmentId: string, status?: OrderStatus): Observable<OrderListResponse> {
    let params = new HttpParams().set('limit', 150);
    if (status) {
      params = params.set('status', status);
    }
    return this.http.get<OrderListResponse>(`${this.baseUrl}/establishments/${establishmentId}/orders`, { params });
  }

  /** Pedidos novos esperando aceite (sino do topo) */
  pendingCount(establishmentId: string): Observable<{ new_orders: number }> {
    return this.http.get<{ new_orders: number }>(`${this.baseUrl}/establishments/${establishmentId}/orders/pending-count`);
  }

  orderBoard(establishmentId: string): Observable<OrderListResponse> {
    return this.http.get<OrderListResponse>(`${this.baseUrl}/establishments/${establishmentId}/orders/board`);
  }

  updatePaymentStatus(establishmentId: string, orderId: string, paymentStatus: PaymentStatus): Observable<Order> {
    return this.http.patch<Order>(`${this.baseUrl}/establishments/${establishmentId}/orders/${orderId}/payment`, {
      payment_status: paymentStatus
    });
  }

  updateCategory(establishmentId: string, categoryId: string, payload: Partial<Category>): Observable<Category> {
    return this.http.patch<Category>(`${this.baseUrl}/establishments/${establishmentId}/categories/${categoryId}`, payload);
  }

  deleteCategory(establishmentId: string, categoryId: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/establishments/${establishmentId}/categories/${categoryId}`);
  }

  order(establishmentId: string, orderId: string): Observable<Order> {
    return this.http.get<Order>(`${this.baseUrl}/establishments/${establishmentId}/orders/${orderId}`);
  }

  createOrder(establishmentId: string, payload: unknown): Observable<Order> {
    return this.http.post<Order>(`${this.baseUrl}/establishments/${establishmentId}/orders`, payload);
  }

  updateOrderStatus(
    establishmentId: string,
    orderId: string,
    status: OrderStatus,
    cancelReason?: string,
    courierId?: string | null,
    cancelCode?: string | null
  ): Observable<Order> {
    return this.http.patch<Order>(`${this.baseUrl}/establishments/${establishmentId}/orders/${orderId}/status`, {
      status,
      cancel_reason: cancelReason,
      courier_id: courierId ?? null,
      cancel_code: cancelCode ?? null
    });
  }

  // ---------------------------------------------------------------- integracao iFood

  ifoodIntegration(establishmentId: string): Observable<IfoodIntegration> {
    return this.http.get<IfoodIntegration>(`${this.baseUrl}/establishments/${establishmentId}/integrations/ifood`);
  }

  /** Liga a loja a uma loja do iFood pelo ID (merchantId). null desconecta. */
  linkIfood(establishmentId: string, merchantId: string | null): Observable<IfoodIntegration> {
    return this.http.put<IfoodIntegration>(`${this.baseUrl}/establishments/${establishmentId}/integrations/ifood`, { merchant_id: merchantId });
  }

  ifoodCancellationReasons(establishmentId: string, orderId: string): Observable<CancellationReason[]> {
    return this.http.get<CancellationReason[]>(`${this.baseUrl}/establishments/${establishmentId}/orders/${orderId}/ifood/cancellation-reasons`);
  }

  categories(establishmentId: string): Observable<Category[]> {
    return this.http.get<Category[]>(`${this.baseUrl}/establishments/${establishmentId}/categories`);
  }

  createCategory(establishmentId: string, payload: Partial<Category>): Observable<Category> {
    return this.http.post<Category>(`${this.baseUrl}/establishments/${establishmentId}/categories`, payload);
  }

  products(establishmentId: string): Observable<Product[]> {
    return this.http.get<Product[]>(`${this.baseUrl}/establishments/${establishmentId}/products`);
  }

  createProduct(establishmentId: string, payload: ProductInput): Observable<Product> {
    return this.http.post<Product>(`${this.baseUrl}/establishments/${establishmentId}/products`, payload);
  }

  updateProduct(establishmentId: string, productId: string, payload: ProductInput): Observable<Product> {
    return this.http.patch<Product>(`${this.baseUrl}/establishments/${establishmentId}/products/${productId}`, payload);
  }

  deleteProduct(establishmentId: string, productId: string): Observable<Product> {
    return this.http.delete<Product>(`${this.baseUrl}/establishments/${establishmentId}/products/${productId}`);
  }

  ingredients(establishmentId: string): Observable<Ingredient[]> {
    return this.http.get<Ingredient[]>(`${this.baseUrl}/establishments/${establishmentId}/ingredients`);
  }

  createIngredient(establishmentId: string, payload: IngredientInput & { name: string }): Observable<Ingredient> {
    return this.http.post<Ingredient>(`${this.baseUrl}/establishments/${establishmentId}/ingredients`, payload);
  }

  updateIngredient(establishmentId: string, ingredientId: string, payload: IngredientInput): Observable<Ingredient> {
    return this.http.patch<Ingredient>(`${this.baseUrl}/establishments/${establishmentId}/ingredients/${ingredientId}`, payload);
  }

  /** PURCHASE soma (chegou mercadoria); ADJUST troca pelo valor contado */
  stockEntry(
    establishmentId: string,
    ingredientId: string,
    payload: { kind: 'PURCHASE' | 'ADJUST'; quantity: number; unit_cost?: number | null; note?: string | null }
  ): Observable<Ingredient> {
    return this.http.post<Ingredient>(`${this.baseUrl}/establishments/${establishmentId}/ingredients/${ingredientId}/stock`, payload);
  }

  stockMovements(establishmentId: string, ingredientId: string): Observable<StockMovement[]> {
    return this.http.get<StockMovement[]>(`${this.baseUrl}/establishments/${establishmentId}/ingredients/${ingredientId}/movements`);
  }

  /** Preco do canal = preco normal + percentual. percent null tira o preco do canal. */
  bulkChannelPrices(
    establishmentId: string,
    payload: { channel: SalesChannel; percent: number | null; round_to_90: boolean; product_ids: string[] }
  ): Observable<Product[]> {
    return this.http.post<Product[]>(`${this.baseUrl}/establishments/${establishmentId}/channel-prices`, payload);
  }

  deleteIngredient(establishmentId: string, ingredientId: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/establishments/${establishmentId}/ingredients/${ingredientId}`);
  }

  /** Pausa/reativa item ou ingrediente por canal. Com dry_run so devolve o que mudaria. */
  changeAvailability(establishmentId: string, payload: AvailabilityRequest): Observable<AvailabilityResponse> {
    return this.http.post<AvailabilityResponse>(`${this.baseUrl}/establishments/${establishmentId}/availability`, payload);
  }

  // ---------------------------------------------------------------- cardapio online (publico, sem login)

  publicStore(slug: string): Observable<PublicStore> {
    return this.http.get<PublicStore>(`${this.baseUrl}/public/stores/${slug}`);
  }

  publicOrder(slug: string, payload: unknown): Observable<{ order_number: string; public_token: string; total: number | string; status: OrderStatus }> {
    return this.http.post<{ order_number: string; public_token: string; total: number | string; status: OrderStatus }>(
      `${this.baseUrl}/public/stores/${slug}/orders`,
      payload
    );
  }

  publicOrderStatus(token: string): Observable<PublicOrderStatus> {
    return this.http.get<PublicOrderStatus>(`${this.baseUrl}/public/orders/${token}`);
  }

  publicCoupon(slug: string, code: string, subtotal: number): Observable<{ valid: boolean; discount: number | string; message: string }> {
    return this.http.post<{ valid: boolean; discount: number | string; message: string }>(`${this.baseUrl}/public/stores/${slug}/coupons/validate`, {
      code,
      subtotal
    });
  }

  // ---------------------------------------------------------------- clientes e cupons

  customers(establishmentId: string, search = ''): Observable<Customer[]> {
    const params = search.trim() ? new HttpParams().set('search', search.trim()) : undefined;
    return this.http.get<Customer[]>(`${this.baseUrl}/establishments/${establishmentId}/customers`, { params });
  }

  /** Cliente pelo telefone (null se nao conhece) */
  customerByPhone(establishmentId: string, phone: string): Observable<Customer | null> {
    return this.http.get<Customer | null>(`${this.baseUrl}/establishments/${establishmentId}/customers/lookup`, {
      params: new HttpParams().set('phone', phone)
    });
  }

  updateCustomer(establishmentId: string, customerId: string, payload: Partial<Customer>): Observable<Customer> {
    return this.http.patch<Customer>(`${this.baseUrl}/establishments/${establishmentId}/customers/${customerId}`, payload);
  }

  coupons(establishmentId: string): Observable<Coupon[]> {
    return this.http.get<Coupon[]>(`${this.baseUrl}/establishments/${establishmentId}/coupons`);
  }

  createCoupon(establishmentId: string, payload: CouponInput): Observable<Coupon> {
    return this.http.post<Coupon>(`${this.baseUrl}/establishments/${establishmentId}/coupons`, payload);
  }

  updateCoupon(establishmentId: string, couponId: string, payload: CouponInput): Observable<Coupon> {
    return this.http.patch<Coupon>(`${this.baseUrl}/establishments/${establishmentId}/coupons/${couponId}`, payload);
  }

  deleteCoupon(establishmentId: string, couponId: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/establishments/${establishmentId}/coupons/${couponId}`);
  }

  /** Previa do desconto de um cupom para este subtotal */
  checkCoupon(establishmentId: string, code: string, subtotal: number): Observable<{ valid: boolean; discount: number | string; message: string }> {
    return this.http.post<{ valid: boolean; discount: number | string; message: string }>(
      `${this.baseUrl}/establishments/${establishmentId}/coupons/validate`,
      { code, subtotal }
    );
  }

  // ---------------------------------------------------------------- entrega

  deliveryZones(establishmentId: string): Observable<DeliveryZone[]> {
    return this.http.get<DeliveryZone[]>(`${this.baseUrl}/establishments/${establishmentId}/delivery-zones`);
  }

  saveDeliveryZone(establishmentId: string, zone: Partial<DeliveryZone>): Observable<DeliveryZone> {
    const url = `${this.baseUrl}/establishments/${establishmentId}/delivery-zones`;
    return zone.id ? this.http.patch<DeliveryZone>(`${url}/${zone.id}`, zone) : this.http.post<DeliveryZone>(url, zone);
  }

  deleteDeliveryZone(establishmentId: string, zoneId: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/establishments/${establishmentId}/delivery-zones/${zoneId}`);
  }

  couriers(establishmentId: string): Observable<Courier[]> {
    return this.http.get<Courier[]>(`${this.baseUrl}/establishments/${establishmentId}/couriers`);
  }

  saveCourier(establishmentId: string, courier: Partial<Courier>): Observable<Courier> {
    const url = `${this.baseUrl}/establishments/${establishmentId}/couriers`;
    return courier.id ? this.http.patch<Courier>(`${url}/${courier.id}`, courier) : this.http.post<Courier>(url, courier);
  }

  deleteCourier(establishmentId: string, courierId: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/establishments/${establishmentId}/couriers/${courierId}`);
  }

  courierReport(establishmentId: string, params: HttpParams): Observable<CourierReportRow[]> {
    return this.http.get<CourierReportRow[]>(`${this.baseUrl}/establishments/${establishmentId}/couriers/report`, { params });
  }

  profitByChannel(establishmentId: string, params: HttpParams): Observable<ProfitByChannel[]> {
    return this.http.get<ProfitByChannel[]>(`${this.baseUrl}/establishments/${establishmentId}/reports/profit-by-channel`, { params });
  }

  /** Caixa aberto (com resumo do turno) ou null */
  currentCash(establishmentId: string): Observable<CashSummary | null> {
    return this.http.get<CashSummary | null>(`${this.baseUrl}/establishments/${establishmentId}/cash/current`);
  }

  openCash(establishmentId: string, openingAmount: number, notes?: string | null): Observable<CashSummary> {
    return this.http.post<CashSummary>(`${this.baseUrl}/establishments/${establishmentId}/cash/open`, { opening_amount: openingAmount, notes });
  }

  cashMovement(establishmentId: string, kind: 'WITHDRAWAL' | 'SUPPLY', amount: number, note?: string | null): Observable<CashSummary> {
    return this.http.post<CashSummary>(`${this.baseUrl}/establishments/${establishmentId}/cash/movements`, { kind, amount, note });
  }

  closeCash(establishmentId: string, countedAmount: number, notes?: string | null): Observable<CashSummary> {
    return this.http.post<CashSummary>(`${this.baseUrl}/establishments/${establishmentId}/cash/close`, { counted_amount: countedAmount, notes });
  }

  cashHistory(establishmentId: string): Observable<CashSummary[]> {
    return this.http.get<CashSummary[]>(`${this.baseUrl}/establishments/${establishmentId}/cash/sessions`);
  }

  simulateOrder(establishmentId: string, source: OrderSource, quantity = 1): Observable<Order[]> {
    return this.http.post<Order[]>(`${this.baseUrl}/dev/establishments/${establishmentId}/simulate-order`, { source, quantity });
  }

  reportOverview(establishmentId: string, params: HttpParams): Observable<ReportOverview> {
    return this.http.get<ReportOverview>(`${this.baseUrl}/establishments/${establishmentId}/reports/overview`, { params });
  }

  salesByChannel(establishmentId: string, params: HttpParams): Observable<Array<{ source: OrderSource; total: number; orders: number }>> {
    return this.http.get<Array<{ source: OrderSource; total: number; orders: number }>>(
      `${this.baseUrl}/establishments/${establishmentId}/reports/sales-by-channel`,
      { params }
    );
  }

  topProducts(establishmentId: string, params: HttpParams): Observable<Array<{ product_name: string; quantity: number; total: number }>> {
    return this.http.get<Array<{ product_name: string; quantity: number; total: number }>>(
      `${this.baseUrl}/establishments/${establishmentId}/reports/top-products`,
      { params }
    );
  }

  setSummariesFromUser(user: AuthUser): EstablishmentSummary[] {
    return user.establishments;
  }
}
