import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { LucideAngularModule } from 'lucide-angular';

import { ApiService } from '../../core/api.service';
import { Product, PublicStore, SalesChannel, SelectedOption } from '../../core/models';
import { ItemOptionsComponent } from '../../shared/item-options.component';
import {
  CartChoice,
  choicesAsSelected,
  choicesPrice,
  errorMessage,
  missingAsSelected,
  missingIngredients,
  roundCents
} from '../../shared/order-options';
import { CustomizedItem, ItemCustomizerComponent } from '../local-order/item-customizer.component';

const CHANNEL: SalesChannel = 'LOCAL';
const SAVED_KEY = 'comandahub.cliente';

interface Line {
  key: number;
  product: Product;
  quantity: number;
  choices: CartChoice[];
  notes: string;
  unitPrice: number;
  display: SelectedOption[];
}

interface SavedCustomer {
  name: string;
  phone: string;
  address: string;
  zoneId: string;
  fulfillment: 'DELIVERY' | 'PICKUP';
}

/** Produto publico no mesmo formato do cardapio interno (para reaproveitar a janela de personalizacao). */
function toProduct(item: PublicStore['products'][number]): Product {
  return {
    ...item,
    establishment_id: '',
    is_available: true,
    paused_channels: [],
    channel_prices: {},
    unit_cost: 0,
    created_at: '',
    updated_at: '',
    ingredients: item.ingredients.map((ingredient) => ({ ...ingredient, quantity: 0, unit: 'un' as const }))
  };
}

/** Cardapio online da loja: o cliente escolhe, monta o pedido e envia (sem login). */
@Component({
  selector: 'app-public-menu',
  standalone: true,
  imports: [CommonModule, FormsModule, LucideAngularModule, ItemCustomizerComponent, ItemOptionsComponent],
  template: `
    <div class="min-h-screen bg-zinc-50 pb-28">
      @if (error()) {
        <div class="mx-auto max-w-md px-4 py-24 text-center">
          <i-lucide class="mx-auto text-zinc-400" name="store" [size]="40" />
          <h1 class="mt-4 text-xl font-extrabold text-zinc-950">Cardapio indisponivel</h1>
          <p class="mt-1 text-sm text-zinc-500">Confira o link com a loja.</p>
        </div>
      }
      @if (store(); as shop) {
        <header class="bg-graphite text-white">
          <div class="mx-auto flex max-w-3xl items-center gap-4 px-4 py-6">
            @if (shop.logo_url) {
              <img class="h-16 w-16 shrink-0 rounded-xl object-cover" [src]="shop.logo_url" [alt]="shop.name" />
            } @else {
              <div class="grid h-16 w-16 shrink-0 place-items-center rounded-xl bg-brand-500"><i-lucide name="utensils" [size]="28" /></div>
            }
            <div class="min-w-0">
              <h1 class="truncate text-2xl font-extrabold">{{ shop.name }}</h1>
              <p class="text-sm text-white/70">{{ shop.opening_hours }}</p>
              <p class="mt-1 text-xs text-white/60">Preparo ~{{ shop.preparation_time }} min{{ shop.delivery_zones.length ? ' - entrega e retirada' : ' - retirada no local' }}</p>
            </div>
          </div>
        </header>

        @if (!shop.accepting_orders) {
          <div class="border-b border-amber-200 bg-amber-50">
            <p class="mx-auto max-w-3xl px-4 py-3 text-sm font-bold text-amber-900">
              Loja fechada no momento. Voce pode ver o cardapio, mas os pedidos voltam quando a loja abrir{{ shop.opening_hours ? ' (' + shop.opening_hours + ')' : '' }}.
            </p>
          </div>
        }

        <nav class="sticky top-0 z-20 border-b border-zinc-200 bg-white/95 backdrop-blur">
          <div class="mx-auto flex max-w-3xl gap-2 overflow-x-auto px-4 py-3">
            @for (category of shop.categories; track category.id) {
              <button type="button" class="focus-ring shrink-0 rounded-full border px-3.5 py-1.5 text-sm font-bold"
                      [ngClass]="activeCategory() === category.id ? 'border-brand-500 bg-brand-500 text-white' : 'border-zinc-200 bg-white text-zinc-700'"
                      (click)="scrollTo(category.id)">{{ category.name }}</button>
            }
          </div>
        </nav>

        <main class="mx-auto max-w-3xl space-y-8 px-4 py-6">
          @for (section of sections(); track section.id) {
            <section [id]="'cat-' + section.id" class="scroll-mt-20">
              <h2 class="mb-3 text-lg font-extrabold text-zinc-950">{{ section.name }}</h2>
              <div class="grid gap-3 sm:grid-cols-2">
                @for (product of section.products; track product.id) {
                  <button type="button" class="focus-ring flex gap-3 rounded-xl border border-zinc-200 bg-white p-3 text-left shadow-sm transition hover:border-brand-300 hover:shadow"
                          (click)="open(product)">
                    <div class="min-w-0 flex-1">
                      <p class="font-extrabold text-zinc-950">{{ product.name }}</p>
                      <p class="mt-0.5 line-clamp-2 text-sm text-zinc-500">{{ product.description }}</p>
                      @if (missing(product).length) {
                        <p class="mt-1 text-xs font-bold text-amber-700">Hoje sem {{ missing(product).join(', ') }}</p>
                      }
                      <p class="mt-2 font-extrabold text-zinc-900">{{ price(product) | currency:'BRL':'symbol':'1.2-2' }}</p>
                    </div>
                    @if (product.image_url) {
                      <img class="h-24 w-24 shrink-0 rounded-lg object-cover" [src]="product.image_url" [alt]="product.name" loading="lazy" />
                    }
                  </button>
                }
              </div>
            </section>
          } @empty {
            <p class="py-16 text-center text-sm text-zinc-500">Nenhum item disponivel agora.</p>
          }
        </main>

        @if (cart().length && !checkout()) {
          <div class="fixed inset-x-0 bottom-0 z-30 border-t border-zinc-200 bg-white p-3 shadow-[0_-4px_20px_rgba(0,0,0,0.06)]">
            <button type="button" class="focus-ring mx-auto flex h-12 w-full max-w-3xl items-center justify-between rounded-xl bg-brand-500 px-4 text-sm font-extrabold text-white hover:bg-brand-600"
                    (click)="checkout.set(true)">
              <span class="inline-flex items-center gap-2"><i-lucide name="shopping-bag" [size]="18" /> Ver sacola ({{ itemCount() }})</span>
              <span>{{ subtotal() | currency:'BRL':'symbol':'1.2-2' }}</span>
            </button>
          </div>
        }

        @if (checkout()) {
          <div class="fixed inset-0 z-40 bg-zinc-950/40" (click)="checkout.set(false)"></div>
          <section class="fixed inset-0 z-40 flex flex-col bg-white sm:inset-y-0 sm:left-auto sm:right-0 sm:w-[460px] sm:shadow-2xl" role="dialog" aria-modal="true" aria-label="Sacola">
            <header class="flex items-center justify-between border-b border-zinc-100 px-5 py-4">
              <h2 class="text-xl font-extrabold text-zinc-950">Sua sacola</h2>
              <button type="button" class="focus-ring rounded-md border border-zinc-200 p-2" (click)="checkout.set(false)" aria-label="Fechar"><i-lucide name="x" [size]="18" /></button>
            </header>
            <div class="flex-1 space-y-5 overflow-y-auto p-5">
              <div class="space-y-3">
                @for (line of cart(); track line.key) {
                  <div class="rounded-lg bg-zinc-50 p-3">
                    <div class="flex justify-between gap-3">
                      <p class="font-bold text-zinc-900">{{ line.quantity }}x {{ line.product.name }}</p>
                      <p class="text-sm font-extrabold">{{ line.unitPrice * line.quantity | currency:'BRL':'symbol':'1.2-2' }}</p>
                    </div>
                    <app-item-options [options]="line.display" />
                    <div class="mt-2 flex items-center justify-end gap-1">
                      <button type="button" class="focus-ring rounded-md border border-zinc-200 bg-white p-2" (click)="changeQty(line, -1)" aria-label="Menos"><i-lucide name="minus" [size]="14" /></button>
                      <button type="button" class="focus-ring rounded-md border border-zinc-200 bg-white p-2" (click)="changeQty(line, 1)" aria-label="Mais"><i-lucide name="plus" [size]="14" /></button>
                    </div>
                  </div>
                }
              </div>

              <div class="grid grid-cols-2 gap-2">
                <button type="button" class="focus-ring h-11 rounded-lg border text-sm font-bold" [disabled]="!shop.delivery_zones.length"
                        [ngClass]="form.fulfillment === 'DELIVERY' ? 'border-brand-500 bg-brand-50 text-brand-800' : 'border-zinc-200 text-zinc-700 disabled:opacity-40'"
                        (click)="form.fulfillment = 'DELIVERY'">Entrega</button>
                <button type="button" class="focus-ring h-11 rounded-lg border text-sm font-bold"
                        [ngClass]="form.fulfillment === 'PICKUP' ? 'border-brand-500 bg-brand-50 text-brand-800' : 'border-zinc-200 text-zinc-700'"
                        (click)="form.fulfillment = 'PICKUP'">Retirar na loja</button>
              </div>

              <div class="space-y-3">
                <label class="block"><span class="mb-1 block text-xs font-bold text-zinc-500">Seu nome</span>
                  <input class="focus-ring h-11 w-full rounded-lg border border-zinc-200 px-3 text-sm" [(ngModel)]="form.name" autocomplete="name" /></label>
                <label class="block"><span class="mb-1 block text-xs font-bold text-zinc-500">WhatsApp / telefone</span>
                  <input class="focus-ring h-11 w-full rounded-lg border border-zinc-200 px-3 text-sm" [(ngModel)]="form.phone" inputmode="tel" autocomplete="tel" placeholder="(11) 99999-9999" /></label>
                @if (form.fulfillment === 'DELIVERY') {
                  <label class="block"><span class="mb-1 block text-xs font-bold text-zinc-500">Bairro</span>
                    <select class="focus-ring h-11 w-full rounded-lg border border-zinc-200 bg-white px-2 text-sm" [(ngModel)]="form.zoneId">
                      <option value="">Escolha o bairro</option>
                      @for (zone of shop.delivery_zones; track zone.id) {
                        <option [value]="zone.id">{{ zone.name }} - {{ num(zone.fee) | currency:'BRL':'symbol':'1.2-2' }}</option>
                      }
                    </select></label>
                  <label class="block"><span class="mb-1 block text-xs font-bold text-zinc-500">Endereco (rua, numero, complemento)</span>
                    <input class="focus-ring h-11 w-full rounded-lg border border-zinc-200 px-3 text-sm" [(ngModel)]="form.address" autocomplete="street-address" /></label>
                }
                <div>
                  <span class="mb-1 block text-xs font-bold text-zinc-500">Pagamento {{ form.fulfillment === 'DELIVERY' ? 'na entrega' : 'na retirada' }}</span>
                  <div class="grid grid-cols-3 gap-2">
                    @for (method of methods; track method.id) {
                      <button type="button" class="focus-ring h-10 rounded-lg border text-sm font-bold"
                              [ngClass]="form.payment === method.id ? 'border-brand-500 bg-brand-50 text-brand-800' : 'border-zinc-200 text-zinc-700'"
                              (click)="form.payment = method.id">{{ method.label }}</button>
                    }
                  </div>
                </div>
                @if (form.payment === 'CASH') {
                  <label class="block"><span class="mb-1 block text-xs font-bold text-zinc-500">Troco para quanto? (opcional)</span>
                    <input class="focus-ring h-11 w-full rounded-lg border border-zinc-200 px-3 text-sm" type="number" min="0" step="0.01" [(ngModel)]="form.changeFor" /></label>
                }
                <label class="block"><span class="mb-1 block text-xs font-bold text-zinc-500">Observacoes (opcional)</span>
                  <input class="focus-ring h-11 w-full rounded-lg border border-zinc-200 px-3 text-sm" maxlength="300" [(ngModel)]="form.notes" /></label>
                <div class="flex gap-2">
                  <input class="focus-ring h-11 min-w-0 flex-1 rounded-lg border border-zinc-200 px-3 text-sm uppercase" placeholder="Cupom" [ngModel]="coupon()" (ngModelChange)="setCoupon($event)" aria-label="Cupom" />
                  <button type="button" class="focus-ring h-11 rounded-lg border border-zinc-200 px-3 text-sm font-bold disabled:opacity-40" [disabled]="!coupon().trim()" (click)="checkCoupon()">Aplicar</button>
                </div>
                @if (couponMessage(); as message) {
                  <p class="-mt-1 text-xs font-bold" [ngClass]="couponDiscount() > 0 ? 'text-emerald-700' : 'text-red-600'">{{ message }}</p>
                }
              </div>
            </div>
            <footer class="border-t border-zinc-100 p-5">
              <div class="space-y-1 text-sm">
                <div class="flex justify-between text-zinc-500"><span>Subtotal</span><span>{{ subtotal() | currency:'BRL':'symbol':'1.2-2' }}</span></div>
                @if (couponDiscount() > 0) {
                  <div class="flex justify-between text-emerald-700"><span>Cupom</span><span>-{{ couponDiscount() | currency:'BRL':'symbol':'1.2-2' }}</span></div>
                }
                @if (form.fulfillment === 'DELIVERY') {
                  <div class="flex justify-between text-zinc-500"><span>Entrega</span><span>{{ deliveryFee() | currency:'BRL':'symbol':'1.2-2' }}</span></div>
                }
                <div class="flex justify-between text-lg font-extrabold text-zinc-950"><span>Total</span><span>{{ total() | currency:'BRL':'symbol':'1.2-2' }}</span></div>
              </div>
              @if (formProblem(); as problem) {
                <p class="mt-2 text-xs font-bold text-zinc-500">{{ problem }}</p>
              }
              <button type="button" class="focus-ring mt-3 inline-flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-brand-500 text-sm font-extrabold text-white hover:bg-brand-600 disabled:opacity-50"
                      [disabled]="!!formProblem() || sending()" (click)="send(shop)">
                <i-lucide name="send" [size]="16" /> {{ sending() ? 'Enviando...' : 'Fazer pedido' }}
              </button>
            </footer>
          </section>
        }

        @if (customizing(); as product) {
          <app-item-customizer [product]="product" channel="LOCAL" (confirmed)="addCustomized(product, $event)" (closed)="customizing.set(null)" />
        }
      }
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class PublicMenuComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private nextKey = 1;

  readonly methods: Array<{ id: 'PIX' | 'CARD' | 'CASH'; label: string }> = [
    { id: 'PIX', label: 'Pix' },
    { id: 'CARD', label: 'Cartao' },
    { id: 'CASH', label: 'Dinheiro' }
  ];
  readonly store = signal<PublicStore | null>(null);
  readonly products = signal<Product[]>([]);
  readonly error = signal(false);
  readonly cart = signal<Line[]>([]);
  readonly checkout = signal(false);
  readonly customizing = signal<Product | null>(null);
  readonly activeCategory = signal<string | null>(null);
  readonly sending = signal(false);
  readonly coupon = signal('');
  readonly couponDiscount = signal(0);
  readonly couponMessage = signal<string | null>(null);
  form = { name: '', phone: '', address: '', zoneId: '', fulfillment: 'DELIVERY' as 'DELIVERY' | 'PICKUP', payment: 'PIX' as 'PIX' | 'CARD' | 'CASH', changeFor: null as number | null, notes: '' };

  readonly sections = computed(() => {
    const shop = this.store();
    if (!shop) return [];
    return shop.categories
      .map((category) => ({ id: category.id, name: category.name, products: this.products().filter((product) => product.category_id === category.id) }))
      .filter((section) => section.products.length);
  });
  readonly subtotal = computed(() => roundCents(this.cart().reduce((sum, line) => sum + line.unitPrice * line.quantity, 0)));
  readonly itemCount = computed(() => this.cart().reduce((sum, line) => sum + line.quantity, 0));

  ngOnInit(): void {
    const slug = this.route.snapshot.paramMap.get('slug') ?? '';
    this.api.publicStore(slug).subscribe({
      next: (shop) => {
        this.store.set(shop);
        this.products.set(shop.products.map(toProduct));
        this.activeCategory.set(shop.categories[0]?.id ?? null);
        if (!shop.delivery_zones.length) this.form.fulfillment = 'PICKUP';
        document.title = `${shop.name} - Cardapio`;
      },
      error: () => this.error.set(true)
    });
    this.restoreCustomer();
  }

  num(value: number | string | null | undefined): number {
    return Number(value ?? 0);
  }

  price(product: Product): number {
    return Number(product.price);
  }

  missing(product: Product): string[] {
    return missingIngredients(product, CHANNEL);
  }

  scrollTo(categoryId: string): void {
    this.activeCategory.set(categoryId);
    document.getElementById(`cat-${categoryId}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  open(product: Product): void {
    if (product.option_groups.length) {
      this.customizing.set(product);
    } else {
      this.addLine(product, { choices: [], notes: '', quantity: 1 });
    }
  }

  addCustomized(product: Product, item: CustomizedItem): void {
    this.addLine(product, item);
    this.customizing.set(null);
  }

  changeQty(line: Line, delta: number): void {
    this.cart.update((lines) => lines.map((item) => (item.key === line.key ? { ...item, quantity: item.quantity + delta } : item)).filter((item) => item.quantity > 0));
    if (!this.cart().length) this.checkout.set(false);
    this.refreshCoupon();
  }

  deliveryFee(): number {
    const zone = this.store()?.delivery_zones.find((item) => item.id === this.form.zoneId);
    return this.form.fulfillment === 'DELIVERY' && zone ? Number(zone.fee) : 0;
  }

  total(): number {
    return roundCents(Math.max(0, this.subtotal() - this.couponDiscount()) + this.deliveryFee());
  }

  formProblem(): string | null {
    if (this.store() && !this.store()!.accepting_orders) return 'A loja esta fechada agora.';
    if (this.form.name.trim().length < 2) return 'Informe seu nome.';
    if (this.form.phone.replace(/\D/g, '').length < 10) return 'Informe seu telefone com DDD.';
    if (this.form.fulfillment === 'DELIVERY') {
      if (!this.form.zoneId) return 'Escolha o bairro.';
      if (this.form.address.trim().length < 5) return 'Informe o endereco.';
    }
    return null;
  }

  setCoupon(value: string): void {
    this.coupon.set(value.toUpperCase());
    this.couponDiscount.set(0);
    this.couponMessage.set(null);
  }

  checkCoupon(): void {
    const shop = this.store();
    if (!shop || !this.coupon().trim()) return;
    this.api.publicCoupon(shop.slug, this.coupon().trim(), this.subtotal()).subscribe({
      next: (result) => {
        this.couponDiscount.set(result.valid ? Number(result.discount) : 0);
        this.couponMessage.set(result.message);
      }
    });
  }

  send(shop: PublicStore): void {
    if (this.formProblem()) return;
    this.sending.set(true);
    this.saveCustomer();
    const payload = {
      customer_name: this.form.name.trim(),
      customer_phone: this.form.phone.trim(),
      fulfillment_type: this.form.fulfillment,
      delivery_address: this.form.fulfillment === 'DELIVERY' ? this.form.address.trim() : null,
      delivery_zone_id: this.form.fulfillment === 'DELIVERY' ? this.form.zoneId : null,
      payment_method: this.form.payment,
      change_for: this.form.payment === 'CASH' && this.form.changeFor ? Number(this.form.changeFor) : null,
      notes: this.form.notes.trim() || null,
      coupon_code: this.couponDiscount() > 0 ? this.coupon().trim() : null,
      items: this.cart().map((line) => ({
        product_id: line.product.id,
        quantity: line.quantity,
        options: line.choices.map((choice) => ({ option_id: choice.optionId, quantity: choice.quantity, notes: choice.notes || null })),
        notes: line.notes || null
      }))
    };
    this.api.publicOrder(shop.slug, payload).subscribe({
      next: (created) => {
        this.sending.set(false);
        this.cart.set([]);
        this.router.navigate(['/pedido', created.public_token]);
      },
      error: (err) => {
        this.sending.set(false);
        window.alert(errorMessage(err, 'Nao foi possivel enviar o pedido. Tente de novo.'));
      }
    });
  }

  private refreshCoupon(): void {
    if (this.couponDiscount() > 0) this.checkCoupon();
  }

  private addLine(product: Product, item: CustomizedItem): void {
    const selected = choicesAsSelected(product, item.choices);
    this.cart.update((lines) => [
      ...lines,
      {
        key: this.nextKey++,
        product,
        quantity: item.quantity,
        choices: item.choices,
        notes: item.notes,
        unitPrice: roundCents(Number(product.price) + choicesPrice(product, item.choices)),
        display: [...selected, ...missingAsSelected(product, CHANNEL, selected)]
      }
    ]);
    this.refreshCoupon();
  }

  /** Lembra os dados do cliente neste aparelho para o proximo pedido. */
  private saveCustomer(): void {
    const saved: SavedCustomer = { name: this.form.name, phone: this.form.phone, address: this.form.address, zoneId: this.form.zoneId, fulfillment: this.form.fulfillment };
    try {
      localStorage.setItem(SAVED_KEY, JSON.stringify(saved));
    } catch {
      /* navegador sem armazenamento: so nao lembra */
    }
  }

  private restoreCustomer(): void {
    try {
      const saved = JSON.parse(localStorage.getItem(SAVED_KEY) ?? 'null') as SavedCustomer | null;
      if (saved) this.form = { ...this.form, name: saved.name ?? '', phone: saved.phone ?? '', address: saved.address ?? '', zoneId: saved.zoneId ?? '', fulfillment: saved.fulfillment ?? 'DELIVERY' };
    } catch {
      /* ignora */
    }
  }
}
