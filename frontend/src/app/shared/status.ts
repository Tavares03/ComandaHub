import { FulfillmentType, OrderSource, OrderStatus, PaymentMethod, PaymentStatus } from '../core/models';

export const ORDER_COLUMNS: Array<{ status: OrderStatus; title: string; hint: string }> = [
  { status: 'NEW', title: 'Novos', hint: 'Aguardando aceite' },
  { status: 'ACCEPTED', title: 'Aceitos', hint: 'Fila de preparo' },
  { status: 'PREPARING', title: 'Em preparo', hint: 'Cozinha trabalhando' },
  { status: 'READY', title: 'Prontos', hint: 'Retirada ou despacho' },
  { status: 'OUT_FOR_DELIVERY', title: 'Saiu entrega', hint: 'Em rota' },
  { status: 'FINISHED', title: 'Finalizados', hint: 'Encerrados' }
];

export function statusLabel(status: OrderStatus): string {
  return {
    NEW: 'Novo',
    ACCEPTED: 'Aceito',
    PREPARING: 'Em preparo',
    READY: 'Pronto',
    OUT_FOR_DELIVERY: 'Saiu para entrega',
    FINISHED: 'Finalizado',
    CANCELED: 'Cancelado'
  }[status];
}

export function sourceLabel(source: OrderSource): string {
  return {
    IFOOD: 'iFood',
    NINETY_NINE_FOOD: '99Food',
    OWN_DELIVERY: 'Delivery proprio',
    COUNTER: 'Balcao',
    STORE_PICKUP: 'Retirada'
  }[source];
}

export function fulfillmentLabel(value: FulfillmentType): string {
  return { DELIVERY: 'Delivery', PICKUP: 'Retirada', COUNTER: 'Balcao' }[value];
}

export function paymentMethodLabel(value: PaymentMethod): string {
  return { CASH: 'Dinheiro', CARD: 'Cartao', PIX: 'Pix', ONLINE: 'Online' }[value];
}

export function paymentStatusLabel(value: PaymentStatus): string {
  return { PENDING: 'Pendente', PAID: 'Pago', FAILED: 'Falhou', REFUNDED: 'Estornado' }[value];
}

export function sourceClass(source: OrderSource): string {
  return {
    IFOOD: 'bg-red-50 text-red-700 ring-red-200',
    NINETY_NINE_FOOD: 'bg-yellow-50 text-yellow-800 ring-yellow-200',
    OWN_DELIVERY: 'bg-sky-50 text-sky-700 ring-sky-200',
    COUNTER: 'bg-zinc-100 text-zinc-700 ring-zinc-200',
    STORE_PICKUP: 'bg-emerald-50 text-emerald-700 ring-emerald-200'
  }[source];
}

export function statusClass(status: OrderStatus): string {
  return {
    NEW: 'bg-brand-50 text-brand-700 ring-brand-100',
    ACCEPTED: 'bg-blue-50 text-blue-700 ring-blue-100',
    PREPARING: 'bg-amber-50 text-amber-700 ring-amber-100',
    READY: 'bg-emerald-50 text-emerald-700 ring-emerald-100',
    OUT_FOR_DELIVERY: 'bg-indigo-50 text-indigo-700 ring-indigo-100',
    FINISHED: 'bg-zinc-100 text-zinc-700 ring-zinc-200',
    CANCELED: 'bg-red-50 text-red-700 ring-red-100'
  }[status];
}

/** marketplaceDelivery: entregador do iFood retira na loja (a loja nao despacha) */
export function nextStatuses(status: OrderStatus, fulfillment: FulfillmentType, marketplaceDelivery = false): OrderStatus[] {
  if (status === 'NEW') return ['ACCEPTED', 'CANCELED'];
  if (status === 'ACCEPTED') return ['PREPARING', 'CANCELED'];
  if (status === 'PREPARING') return ['READY', 'CANCELED'];
  if (status === 'READY') return fulfillment === 'DELIVERY' && !marketplaceDelivery ? ['OUT_FOR_DELIVERY', 'CANCELED'] : ['FINISHED', 'CANCELED'];
  if (status === 'OUT_FOR_DELIVERY') return ['FINISHED', 'CANCELED'];
  return [];
}

const EVENT_LABELS: Record<string, string> = {
  ORDER_CREATED: 'Pedido criado',
  ORDER_STATUS_CHANGED: 'Status alterado',
  PAYMENT_STATUS_CHANGED: 'Pagamento atualizado',
  IFOOD_CANCELLATION_REQUESTED: 'Cancelamento solicitado ao iFood',
  IFOOD_CANCELLATION_REQUEST_FAILED: 'iFood recusou o cancelamento',
  IFOOD_SYNC_WARNING: 'Aviso na sincronizacao com o iFood',
  IFOOD_ASSIGN_DRIVER: 'iFood: entregador designado',
  IFOOD_GOING_TO_ORIGIN: 'iFood: entregador a caminho da loja',
  IFOOD_ARRIVED_AT_ORIGIN: 'iFood: entregador chegou na loja',
  IFOOD_COLLECTED: 'iFood: pedido coletado',
  IFOOD_ARRIVED_AT_DESTINATION: 'iFood: entregador chegou no cliente'
};

/** Nome amigavel do evento do historico (eventos novos do iFood aparecem como "iFood: CODIGO") */
export function eventLabel(eventType: string): string {
  if (EVENT_LABELS[eventType]) return EVENT_LABELS[eventType];
  if (eventType.startsWith('IFOOD_')) return `iFood: ${eventType.slice(6).replace(/_/g, ' ').toLowerCase()}`;
  return eventType;
}

/** Tempo desde a criacao do pedido: "8 min", "2 h 05 min", "3 dias" */
export function waitLabel(createdAt: string, now = Date.now()): string {
  const minutes = Math.max(0, Math.floor((now - new Date(createdAt).getTime()) / 60000));
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} h ${String(minutes % 60).padStart(2, '0')} min`;
  const days = Math.floor(hours / 24);
  return days === 1 ? '1 dia' : `${days} dias`;
}
