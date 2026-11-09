export type UserRole = 'ADMIN' | 'ATTENDANT' | 'KITCHEN';
export type OrderSource = 'IFOOD' | 'NINETY_NINE_FOOD' | 'OWN_DELIVERY' | 'COUNTER' | 'STORE_PICKUP';
export type FulfillmentType = 'DELIVERY' | 'PICKUP' | 'COUNTER';
export type PaymentMethod = 'CASH' | 'CARD' | 'PIX' | 'ONLINE';
export type PaymentStatus = 'PENDING' | 'PAID' | 'FAILED' | 'REFUNDED';
export type OrderStatus = 'NEW' | 'ACCEPTED' | 'PREPARING' | 'READY' | 'OUT_FOR_DELIVERY' | 'FINISHED' | 'CANCELED';

export interface EstablishmentSummary {
  id: string;
  name: string;
  role: UserRole;
}

export interface AuthUser {
  id: string;
  name: string;
  email: string;
  is_active: boolean;
  created_at: string;
  establishments: EstablishmentSummary[];
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export interface Establishment extends EstablishmentSummary {
  legal_name?: string | null;
  tax_id?: string | null;
  phone?: string | null;
  address?: string | null;
  opening_hours?: string | null;
  logo_url?: string | null;
  timezone: string;
  preparation_time: number;
  /** Fidelidade: a cada loyalty_goal pedidos, o proximo ganha loyalty_reward de desconto */
  loyalty_enabled: boolean;
  loyalty_goal: number;
  loyalty_reward: number | string;
  /** Comissao de cada canal em % (relatorio de lucro) */
  channel_commissions: Partial<Record<SalesChannel, number | string>>;
  /** Cardapio online: /cardapio/<slug> */
  slug?: string | null;
  whatsapp?: string | null;
  online_menu_enabled: boolean;
  /** Loja aberta para pedidos online agora */
  online_orders_open: boolean;
  created_at: string;
  updated_at: string;
}

export interface Category {
  id: string;
  establishment_id: string;
  name: string;
  sort_order: number;
}

/** Onde o item e vendido. LOCAL = balcao, retirada e delivery proprio. */
export type SalesChannel = 'IFOOD' | 'NINETY_NINE_FOOD' | 'LOCAL';

/** SUM: soma tudo. MAX: cobra so a escolha mais cara (pizza meio a meio). AVERAGE: cobra a media. */
export type OptionPricingMode = 'SUM' | 'MAX' | 'AVERAGE';

export interface ProductOption {
  id: string;
  name: string;
  price_delta: number | string;
  is_available: boolean;
  sort_order: number;
  /** Canais em que esta opcao esta pausada (ex.: batata do combo pausada no 99) */
  paused_channels: SalesChannel[];
  /** A opcao "e" este produto do cardapio (batata do combo = produto Batata Frita) */
  linked_product_id?: string | null;
  /** A opcao usa este ingrediente (Sem alface, Bacon extra) */
  ingredient_id?: string | null;
  /** Quanto do ingrediente a opcao gasta (Bacon extra = 0,03 kg) */
  ingredient_quantity?: number | string;
}

export interface ProductOptionGroup {
  id: string;
  name: string;
  min_choices: number;
  /** 0 = sem limite */
  max_choices: number;
  sort_order: number;
  pricing_mode: OptionPricingMode;
  allow_repeat: boolean;
  /** Grupo condicional: so aparece quando esta opcao foi escolhida (ex.: bebida do combo) */
  depends_on_option_id?: string | null;
  options: ProductOption[];
}

export interface ProductOptionInput {
  /** Com id a opcao existente e mantida (id e pausas); sem id e criada */
  id?: string;
  name: string;
  price_delta: number;
  is_available: boolean;
  linked_product_id?: string | null;
  ingredient_id?: string | null;
  ingredient_quantity?: number;
}

/** Formato de envio ao salvar um produto: a ordem da lista define a ordem de exibicao. */
export interface ProductOptionGroupInput {
  id?: string;
  name: string;
  min_choices: number;
  max_choices: number;
  pricing_mode: OptionPricingMode;
  allow_repeat: boolean;
  /** Posicao (no proprio envio) da opcao que libera este grupo; precisa ser de um grupo anterior */
  depends_on?: { group: number; option: number } | null;
  options: ProductOptionInput[];
}

export type IngredientUnit = 'un' | 'kg' | 'g' | 'L' | 'ml';

export interface Ingredient {
  id: string;
  establishment_id: string;
  name: string;
  unit: IngredientUnit;
  /** null = nao controla estoque */
  stock_quantity: number | string | null;
  min_stock: number | string | null;
  cost_per_unit: number | string;
  /** Estoque zerou e o sistema pausou sozinho */
  auto_paused: boolean;
}

export interface IngredientInput {
  name?: string;
  unit?: IngredientUnit;
  stock_quantity?: number | null;
  min_stock?: number | null;
  cost_per_unit?: number;
  track_stock?: boolean;
}

export interface StockMovement {
  id: string;
  /** ORDER (pedido), CANCEL (cancelamento), PURCHASE (entrada), ADJUST (contagem) */
  reason: 'ORDER' | 'CANCEL' | 'PURCHASE' | 'ADJUST';
  delta: number | string;
  balance: number | string;
  order_id?: string | null;
  unit_cost?: number | string | null;
  note?: string | null;
  created_at: string;
}

export interface ProductIngredient {
  ingredient_id: string;
  name: string;
  /** Principal: se acabar, o item sai do cardapio. Senao vende sem ele. */
  essential: boolean;
  /** Ficha tecnica: quanto vai em uma unidade do item */
  quantity: number | string;
  unit: IngredientUnit;
  paused_channels: SalesChannel[];
}

export interface ProductInput {
  category_id?: string;
  name?: string;
  description?: string | null;
  price?: number;
  image_url?: string | null;
  is_available?: boolean;
  option_groups?: ProductOptionGroupInput[];
  ingredients?: Array<{ ingredient_id: string; essential: boolean; quantity: number }>;
  channel_prices?: Partial<Record<SalesChannel, number>>;
}

export interface Product {
  id: string;
  establishment_id: string;
  category_id: string;
  name: string;
  description?: string | null;
  price: number | string;
  image_url?: string | null;
  is_available: boolean;
  created_at: string;
  updated_at: string;
  paused_channels: SalesChannel[];
  /** Preco por canal; canal ausente usa price */
  channel_prices: Partial<Record<SalesChannel, number | string>>;
  /** Custo da ficha tecnica */
  unit_cost: number | string;
  category?: Category | null;
  option_groups: ProductOptionGroup[];
  ingredients: ProductIngredient[];
}

export type AvailabilityScope = 'item' | 'everywhere' | 'selected';

export interface AvailabilityRequest {
  target_type: 'product' | 'ingredient';
  target_id: string;
  action: 'pause' | 'resume';
  channels: SalesChannel[];
  /** Item: so ele (item) ou tambem dentro dos combos (everywhere). Ingrediente: todos os itens (everywhere) ou alguns (selected). */
  scope: AvailabilityScope;
  product_ids?: string[];
  all_establishments?: boolean;
  /** So mostra o que vai mudar, sem gravar */
  dry_run?: boolean;
}

export interface AvailabilityResponse {
  results: Array<{
    establishment_id: string;
    establishment_name: string;
    changes: Array<{ product_name: string; what: string }>;
  }>;
  not_found_in: string[];
}

export interface OrderItem {
  id: string;
  product_id?: string | null;
  product_name: string;
  quantity: number;
  unit_price: number | string;
  total: number | string;
  notes?: string | null;
  selected_options: SelectedOption[];
  unit_cost?: number | string | null;
}

/** Retrato de uma escolha gravado no item. Pedidos antigos so tem name e price_delta. */
export interface SelectedOption {
  name: string;
  price_delta: string;
  option_id?: string | null;
  group_id?: string | null;
  group_name?: string;
  pricing_mode?: OptionPricingMode;
  quantity?: number;
  notes?: string | null;
}

export interface OrderEvent {
  id: string;
  event_type: string;
  previous_status?: OrderStatus | null;
  new_status?: OrderStatus | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface Order {
  customer_id?: string | null;
  coupon_code?: string | null;
  delivery_zone_id?: string | null;
  neighborhood?: string | null;
  courier_id?: string | null;
  courier_name?: string | null;
  id: string;
  establishment_id: string;
  external_order_id?: string | null;
  source: OrderSource;
  order_number: string;
  customer_name?: string | null;
  customer_phone?: string | null;
  delivery_address?: string | null;
  fulfillment_type: FulfillmentType;
  payment_method: PaymentMethod;
  payment_status: PaymentStatus;
  status: OrderStatus;
  subtotal: number | string;
  discount: number | string;
  delivery_fee: number | string;
  total: number | string;
  notes?: string | null;
  created_at: string;
  updated_at: string;
  items: OrderItem[];
  events: OrderEvent[];
}

export interface OrderListResponse {
  items: Order[];
  total: number;
  limit: number;
  offset: number;
}

export interface DashboardResponse {
  orders_today: number;
  in_progress: number;
  finished_today: number;
  canceled_today: number;
  gross_revenue_today: number;
  average_ticket_today: number;
  sales_by_channel: Array<{ source: OrderSource; total: number; orders: number }>;
  orders_by_hour: Array<{ hour: number; orders: number }>;
  sales_last_7_days: Array<{ date: string; total: number }>;
  recent_orders: Order[];
}

export interface ReportOverview {
  total_sold: number;
  order_count: number;
  average_ticket: number;
  canceled_count: number;
  in_progress_count: number;
  finished_count: number;
}

export interface EstablishmentUser {
  id: string;
  name: string;
  email: string;
  is_active: boolean;
  role: UserRole;
}

export interface CashMovement {
  id: string;
  /** WITHDRAWAL = sangria, SUPPLY = reforco */
  kind: 'WITHDRAWAL' | 'SUPPLY';
  amount: number | string;
  note?: string | null;
  user_name?: string | null;
  created_at: string;
}

export interface CashSummary {
  id: string;
  opened_at: string;
  opened_by_name?: string | null;
  opening_amount: number | string;
  closed_at?: string | null;
  closed_by_name?: string | null;
  counted_amount?: number | string | null;
  notes?: string | null;
  order_count: number;
  canceled_count: number;
  total_sales: number | string;
  sales_by_method: Array<{ payment_method: PaymentMethod; orders: number; total: number | string }>;
  withdrawals: number | string;
  supplies: number | string;
  /** Troco + vendas em dinheiro + reforcos - sangrias */
  expected_cash: number | string;
  /** Contado - esperado (negativo = faltou) */
  difference?: number | string | null;
  movements: CashMovement[];
}

export interface Customer {
  id: string;
  name: string;
  phone: string;
  address?: string | null;
  neighborhood?: string | null;
  notes?: string | null;
  loyalty_points: number;
  /** Ja pode usar a recompensa da fidelidade */
  reward_available: boolean;
  order_count: number;
  total_spent: number | string;
  last_order_at?: string | null;
  created_at: string;
}

export interface Coupon {
  id: string;
  code: string;
  /** PERCENT = % do subtotal, FIXED = valor em R$ */
  kind: 'PERCENT' | 'FIXED';
  value: number | string;
  min_order: number | string;
  max_uses?: number | null;
  uses: number;
  valid_until?: string | null;
  active: boolean;
  created_at: string;
}

export interface CouponInput {
  code?: string;
  kind?: 'PERCENT' | 'FIXED';
  value?: number;
  min_order?: number;
  max_uses?: number | null;
  valid_until?: string | null;
  active?: boolean;
}

export interface DeliveryZone {
  id: string;
  name: string;
  fee: number | string;
  estimated_minutes?: number | null;
  active: boolean;
}

export interface Courier {
  id: string;
  name: string;
  phone?: string | null;
  /** Quanto recebe por entrega (0 = recebe a taxa cobrada) */
  fee_per_delivery: number | string;
  active: boolean;
}

export interface CourierReportRow {
  courier_id: string;
  name: string;
  deliveries: number;
  fees_charged: number | string;
  to_pay: number | string;
}

export interface ProfitByChannel {
  channel: SalesChannel;
  orders: number;
  revenue: number | string;
  commission_rate: number | string;
  commission: number | string;
  ingredient_cost: number | string;
  profit: number | string;
  margin: number | string;
}

/** Cardapio publico da loja (sem login) */
export interface PublicStore {
  name: string;
  slug: string;
  phone?: string | null;
  whatsapp?: string | null;
  address?: string | null;
  opening_hours?: string | null;
  logo_url?: string | null;
  preparation_time: number;
  /** false = loja fechada agora (mostra o cardapio, mas nao aceita pedido) */
  accepting_orders: boolean;
  loyalty_enabled: boolean;
  loyalty_goal: number;
  loyalty_reward: number | string;
  categories: Array<{ id: string; name: string; sort_order: number }>;
  products: Array<{
    id: string;
    category_id: string;
    name: string;
    description?: string | null;
    price: number | string;
    image_url?: string | null;
    option_groups: ProductOptionGroup[];
    ingredients: Array<{ ingredient_id: string; name: string; essential: boolean; paused_channels: SalesChannel[] }>;
  }>;
  delivery_zones: Array<{ id: string; name: string; fee: number | string; estimated_minutes?: number | null }>;
}

export interface PublicOrderStatus {
  order_number: string;
  status: OrderStatus;
  fulfillment_type: FulfillmentType;
  payment_method: PaymentMethod;
  subtotal: number | string;
  discount: number | string;
  delivery_fee: number | string;
  total: number | string;
  created_at: string;
  customer_name?: string | null;
  delivery_address?: string | null;
  items: Array<{ quantity: number; product_name: string; total: number | string; options: string[] }>;
  store_name: string;
  store_slug?: string | null;
  store_whatsapp?: string | null;
  store_phone?: string | null;
  preparation_time: number;
}
