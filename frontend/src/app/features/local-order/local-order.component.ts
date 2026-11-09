import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, effect, inject, signal, untracked } from '@angular/core';
import { RouterLink } from '@angular/router';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { LucideAngularModule } from 'lucide-angular';

import { ApiService } from '../../core/api.service';
import { Category, Customer, DeliveryZone, Product, SalesChannel, SelectedOption } from '../../core/models';
import { TenantService } from '../../core/tenant.service';
import { ToastService } from '../../core/toast.service';
import { ItemOptionsComponent } from '../../shared/item-options.component';
import {
  CartChoice,
  choicesAsSelected,
  choicesPrice,
  errorMessage,
  missingAsSelected,
  missingIngredients,
  priceFor,
  productBlockReason,
  roundCents
} from '../../shared/order-options';
import { CustomizedItem, ItemCustomizerComponent } from './item-customizer.component';

interface CartLine {
  key: number;
  product: Product;
  quantity: number;
  choices: CartChoice[];
  notes: string;
  unitPrice: number;
  display: SelectedOption[];
}

/** Produto aberto na janela de personalizacao: novo item (line null) ou edicao de uma linha. */
interface Customizing {
  product: Product;
  line: CartLine | null;
}

interface ProductSection {
  id: string;
  name: string;
  products: Product[];
}

/** Pedido local vende pelo canal LOCAL (balcao, retirada, delivery proprio). */
const CHANNEL: SalesChannel = 'LOCAL';
const NO_CATEGORY = '__none__';

@Component({
  selector: 'app-local-order',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink, LucideAngularModule, ItemCustomizerComponent, ItemOptionsComponent],
  template: `
    <section class="grid gap-5 xl:grid-cols-[1fr_390px]">
      <div class="min-w-0 space-y-5">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 class="text-2xl font-extrabold tracking-normal text-zinc-950">Pedido local</h1>
            <p class="mt-1 text-sm text-zinc-500">Monte pedidos de balcao, retirada ou delivery proprio.</p>
          </div>
          <label class="relative block w-full sm:w-80">
            <i-lucide class="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" name="search" [size]="18" />
            <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 bg-white pl-10 pr-3 text-sm" placeholder="Buscar produto" [value]="search()" (input)="search.set($any($event.target).value)" />
          </label>
        </div>

        @if (cashClosed()) {
          <a routerLink="/cash" class="focus-ring flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm font-bold text-amber-900 hover:bg-amber-100">
            <i-lucide name="lock" [size]="16" /> O caixa esta fechado. Clique para abrir antes de vender.
          </a>
        }

        <div class="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1 sm:flex-wrap sm:overflow-visible" role="tablist" aria-label="Filtrar por categoria">
          <button type="button" role="tab" class="focus-ring shrink-0 rounded-full border px-3.5 py-1.5 text-sm font-bold"
                  [attr.aria-selected]="selectedCategory() === null"
                  [ngClass]="selectedCategory() === null ? 'border-brand-500 bg-brand-500 text-white' : 'border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50'"
                  (click)="selectedCategory.set(null)">
            Todos <span class="ml-1 opacity-70">{{ products().length }}</span>
          </button>
          @for (chip of categoryChips(); track chip.id) {
            <button type="button" role="tab" class="focus-ring shrink-0 rounded-full border px-3.5 py-1.5 text-sm font-bold"
                    [attr.aria-selected]="selectedCategory() === chip.id"
                    [ngClass]="selectedCategory() === chip.id ? 'border-brand-500 bg-brand-500 text-white' : 'border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50'"
                    (click)="selectedCategory.set(chip.id)">
              {{ chip.name }} <span class="ml-1 opacity-70">{{ chip.count }}</span>
            </button>
          }
        </div>

        @for (section of sections(); track section.id) {
          <div class="space-y-3">
            @if (selectedCategory() === null) {
              <h2 class="text-sm font-extrabold uppercase tracking-wide text-zinc-500">{{ section.name }}</h2>
            }
            <div class="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
              @for (product of section.products; track product.id) {
                <article class="app-card overflow-hidden" [class.opacity-60]="blockReason(product)">
                  <div class="relative h-36 bg-zinc-200">
                    @if (product.image_url) {
                      <img class="h-full w-full object-cover" [src]="product.image_url" [alt]="product.name" />
                    }
                    @if (blockReason(product); as reason) {
                      <span class="absolute left-3 top-3 inline-flex items-center gap-1 rounded-full bg-red-600 px-2.5 py-1 text-xs font-extrabold text-white shadow-sm">
                        <i-lucide name="circle-pause" [size]="13" /> {{ reason }}
                      </span>
                    } @else if (product.option_groups.length) {
                      <span class="absolute left-3 top-3 inline-flex items-center gap-1 rounded-full bg-white/95 px-2.5 py-1 text-xs font-extrabold text-zinc-800 shadow-sm">
                        <i-lucide name="sliders-horizontal" [size]="13" /> {{ hasCombo(product) ? 'Pode virar combo' : 'Personalizavel' }}
                      </span>
                    }
                  </div>
                  <div class="p-4">
                    <div class="flex items-start justify-between gap-3">
                      <div>
                        <p class="font-extrabold text-zinc-950">{{ product.name }}</p>
                        <p class="mt-1 line-clamp-2 text-sm text-zinc-500">{{ product.description }}</p>
                      </div>
                      <p class="whitespace-nowrap text-sm font-extrabold">{{ price(product) | currency:'BRL':'symbol':'1.2-2' }}</p>
                    </div>
                    @if (missing(product).length) {
                      <p class="mt-2 inline-flex items-center gap-1 rounded bg-amber-50 px-2 py-1 text-xs font-bold text-amber-800">
                        <i-lucide name="triangle-alert" [size]="13" /> Hoje vai sem {{ missing(product).join(', ') }}
                      </p>
                    }
                    <button class="focus-ring mt-4 inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-brand-500 text-sm font-bold text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:bg-zinc-300"
                            [disabled]="!!blockReason(product)" (click)="add(product)">
                      @if (blockReason(product)) {
                        Indisponivel para pedido local
                      } @else if (product.option_groups.length) {
                        <i-lucide name="sliders-horizontal" [size]="16" /> Escolher e adicionar
                      } @else {
                        <i-lucide name="plus" [size]="16" /> Adicionar
                      }
                    </button>
                  </div>
                </article>
              }
            </div>
          </div>
        } @empty {
          <div class="app-card p-8 text-center text-sm text-zinc-500">Nenhum produto disponivel para este filtro.</div>
        }
      </div>

      <aside class="app-card h-max overflow-hidden">
        <div class="border-b border-zinc-100 p-4">
          <div class="flex items-center gap-2">
            <i-lucide class="text-brand-600" name="shopping-cart" [size]="20" />
            <h2 class="text-lg font-extrabold text-zinc-950">Comanda</h2>
          </div>
        </div>
        <form class="space-y-4 p-4" [formGroup]="form" (ngSubmit)="submit()">
          <div class="grid grid-cols-2 gap-3">
            <label class="block">
              <span class="mb-1 block text-xs font-bold text-zinc-500">Tipo</span>
              <select class="focus-ring h-10 w-full rounded-lg border border-zinc-200 bg-white px-3 text-sm" formControlName="fulfillment_type">
                <option value="COUNTER">Balcao</option>
                <option value="PICKUP">Retirada</option>
                <option value="DELIVERY">Delivery proprio</option>
              </select>
            </label>
            <label class="block">
              <span class="mb-1 block text-xs font-bold text-zinc-500">Pagamento</span>
              <select class="focus-ring h-10 w-full rounded-lg border border-zinc-200 bg-white px-3 text-sm" formControlName="payment_method">
                <option value="PIX">Pix</option>
                <option value="CARD">Cartao</option>
                <option value="CASH">Dinheiro</option>
              </select>
            </label>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <label class="block">
              <span class="mb-1 block text-xs font-bold text-zinc-500">Telefone</span>
              <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" formControlName="customer_phone" placeholder="(11) 99999-9999"
                     inputmode="tel" (blur)="lookupCustomer()" (keydown.enter)="$event.preventDefault(); lookupCustomer()" />
            </label>
            <label class="block">
              <span class="mb-1 block text-xs font-bold text-zinc-500">Cliente</span>
              <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" formControlName="customer_name" placeholder="Nome ou mesa" />
            </label>
          </div>

          @if (customer(); as known) {
            <div class="rounded-lg bg-brand-50 px-3 py-2 text-xs text-brand-900">
              <p class="font-bold">Cliente da casa: {{ known.order_count }} pedido(s) - {{ money(known.total_spent) | currency:'BRL':'symbol':'1.2-2' }} no total</p>
              @if (loyaltyEnabled()) {
                @if (known.reward_available) {
                  <label class="mt-1 flex items-center gap-2 font-bold text-emerald-800">
                    <input type="checkbox" [checked]="useReward()" (change)="useReward.set(!useReward())" />
                    Usar recompensa da fidelidade (-{{ loyaltyReward() | currency:'BRL':'symbol':'1.2-2' }})
                  </label>
                } @else {
                  <p class="mt-0.5">Fidelidade: {{ known.loyalty_points }}/{{ loyaltyGoal() }} pedidos</p>
                }
              }
            </div>
          }

          @if (form.controls.fulfillment_type.value === 'DELIVERY') {
            <label class="block">
              <span class="mb-1 block text-xs font-bold text-zinc-500">Endereco</span>
              <textarea class="focus-ring min-h-16 w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm" formControlName="delivery_address"></textarea>
            </label>
            <div class="grid grid-cols-2 gap-3">
              <label class="block">
                <span class="mb-1 block text-xs font-bold text-zinc-500">Bairro</span>
                <select class="focus-ring h-10 w-full rounded-lg border border-zinc-200 bg-white px-2 text-sm" formControlName="delivery_zone_id" (change)="applyZoneFee()">
                  <option value="">Outro / digitar taxa</option>
                  @for (zone of activeZones(); track zone.id) {
                    <option [value]="zone.id">{{ zone.name }} ({{ money(zone.fee) | currency:'BRL':'symbol':'1.2-2' }})</option>
                  }
                </select>
              </label>
              <label class="block">
                <span class="mb-1 block text-xs font-bold text-zinc-500">Taxa de entrega</span>
                <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" type="number" step="0.01" formControlName="delivery_fee" />
              </label>
            </div>
          }

          <div class="flex gap-2">
            <input class="focus-ring h-10 min-w-0 flex-1 rounded-lg border border-zinc-200 px-3 text-sm uppercase" placeholder="Cupom de desconto"
                   [value]="couponCode()" (input)="setCoupon($any($event.target).value)" (keydown.enter)="$event.preventDefault(); checkCoupon()" aria-label="Cupom de desconto" />
            <button type="button" class="focus-ring h-10 rounded-lg border border-zinc-200 px-3 text-sm font-bold hover:bg-zinc-50 disabled:opacity-40"
                    [disabled]="!couponCode().trim()" (click)="checkCoupon()">Aplicar</button>
          </div>
          @if (couponMessage(); as message) {
            <p class="-mt-2 text-xs font-bold" [ngClass]="couponDiscount() > 0 ? 'text-emerald-700' : 'text-red-600'">{{ message }}</p>
          }

          <label class="block">
            <span class="mb-1 block text-xs font-bold text-zinc-500">Observacoes do pedido</span>
            <textarea class="focus-ring min-h-20 w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm" formControlName="notes"></textarea>
          </label>

          <div class="space-y-3 border-t border-zinc-100 pt-4">
            @for (line of cart(); track line.key) {
              <div class="rounded-lg bg-zinc-50 p-3">
                <div class="grid grid-cols-[1fr_auto] gap-3">
                  <div class="min-w-0">
                    <p class="font-bold text-zinc-900">{{ line.quantity }}x {{ line.product.name }}</p>
                    <p class="text-sm text-zinc-500">{{ line.unitPrice | currency:'BRL':'symbol':'1.2-2' }} cada</p>
                  </div>
                  <p class="text-sm font-extrabold text-zinc-900">{{ line.unitPrice * line.quantity | currency:'BRL':'symbol':'1.2-2' }}</p>
                </div>
                <div class="mt-1">
                  <app-item-options [options]="line.display" />
                  @if (line.notes) {
                    <p class="mt-1 rounded bg-amber-50 px-2 py-1 text-xs font-semibold text-amber-800">{{ line.notes }}</p>
                  }
                </div>
                <div class="mt-2 flex items-center justify-end gap-1">
                  <button type="button" class="focus-ring mr-auto inline-flex items-center gap-1 rounded-md border border-zinc-200 bg-white px-2 py-1.5 text-xs font-bold" (click)="editLine(line)">
                    <i-lucide name="edit-3" [size]="13" /> {{ line.product.option_groups.length ? 'Editar' : 'Observacao' }}
                  </button>
                  <button type="button" class="focus-ring rounded-md border border-zinc-200 bg-white p-2" (click)="changeQuantity(line, -1)" aria-label="Diminuir">
                    <i-lucide name="minus" [size]="14" />
                  </button>
                  <button type="button" class="focus-ring rounded-md border border-zinc-200 bg-white p-2" (click)="changeQuantity(line, 1)" aria-label="Aumentar">
                    <i-lucide name="plus" [size]="14" />
                  </button>
                  <button type="button" class="focus-ring rounded-md border border-red-200 bg-white p-2 text-red-600" (click)="remove(line)" aria-label="Remover">
                    <i-lucide name="trash-2" [size]="14" />
                  </button>
                </div>
              </div>
            } @empty {
              <p class="rounded-lg border border-dashed border-zinc-300 p-4 text-center text-sm text-zinc-500">Adicione produtos para criar o pedido.</p>
            }
          </div>

          <div class="rounded-lg bg-zinc-950 p-4 text-white">
            <div class="flex justify-between text-sm text-white/70"><span>Subtotal estimado</span><span>{{ subtotal() | currency:'BRL':'symbol':'1.2-2' }}</span></div>
            @if (discountTotal() > 0) {
              <div class="mt-1 flex justify-between text-sm text-emerald-300"><span>Descontos</span><span>-{{ discountTotal() | currency:'BRL':'symbol':'1.2-2' }}</span></div>
            }
            <div class="mt-2 flex justify-between text-lg font-extrabold"><span>Total estimado</span><span>{{ estimatedTotal() | currency:'BRL':'symbol':'1.2-2' }}</span></div>
          </div>

          <button class="focus-ring inline-flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-brand-500 text-sm font-extrabold text-white hover:bg-brand-600" [disabled]="cart().length === 0 || form.invalid || loading()" type="submit">
            <i-lucide name="send" [size]="16" /> Confirmar pedido
          </button>
        </form>
      </aside>
    </section>

    @if (customizing(); as current) {
      <app-item-customizer
        [product]="current.product"
        [initial]="current.line ? { choices: current.line.choices, notes: current.line.notes, quantity: current.line.quantity } : null"
        (confirmed)="applyCustomization(current, $event)"
        (closed)="customizing.set(null)"
      />
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class LocalOrderComponent {
  private readonly api = inject(ApiService);
  private readonly tenant = inject(TenantService);
  private readonly toast = inject(ToastService);
  private readonly fb = inject(FormBuilder);
  private nextKey = 1;

  readonly products = signal<Product[]>([]);
  readonly categories = signal<Category[]>([]);
  /** Aviso (nao bloqueia): vender com o caixa fechado deixa o turno sem conferencia */
  readonly cashClosed = signal(false);
  readonly zones = signal<DeliveryZone[]>([]);
  readonly customer = signal<Customer | null>(null);
  readonly useReward = signal(false);
  readonly couponCode = signal('');
  readonly couponApplied = signal(false);
  readonly couponDiscount = signal(0);
  readonly couponMessage = signal<string | null>(null);
  readonly loyaltyEnabled = signal(false);
  readonly loyaltyGoal = signal(10);
  readonly loyaltyReward = signal(0);
  readonly activeZones = computed(() => this.zones().filter((zone) => zone.active));
  readonly discountTotal = computed(() => {
    const reward = this.useReward() && this.customer()?.reward_available ? this.loyaltyReward() : 0;
    return roundCents(Math.min(this.couponDiscount() + reward, this.subtotal()));
  });
  /** null = todas as categorias */
  readonly selectedCategory = signal<string | null>(null);
  readonly cart = signal<CartLine[]>([]);
  readonly search = signal('');
  readonly loading = signal(false);
  readonly customizing = signal<Customizing | null>(null);
  readonly form = this.fb.nonNullable.group({
    fulfillment_type: ['COUNTER', Validators.required],
    payment_method: ['PIX', Validators.required],
    payment_status: ['PAID', Validators.required],
    customer_name: [''],
    customer_phone: [''],
    delivery_zone_id: [''],
    delivery_address: [''],
    delivery_fee: [7.9],
    notes: ['']
  });

  constructor() {
    effect(() => {
      this.cart();
      if (untracked(() => this.couponApplied())) untracked(() => this.checkCoupon());
    }, { allowSignalWrites: true });
    effect(() => {
      const establishment = this.tenant.current();
      if (establishment) {
        untracked(() => {
          // Itens de outra loja nao valem aqui
          this.cart.set([]);
          this.customizing.set(null);
          this.selectedCategory.set(null);
          this.loadProducts(establishment.id);
        });
      }
    }, { allowSignalWrites: true });
  }

  loadProducts(establishmentId: string): void {
    this.api.categories(establishmentId).subscribe({ next: (items) => this.categories.set(items) });
    this.api.currentCash(establishmentId).subscribe({ next: (cash) => this.cashClosed.set(!cash), error: () => this.cashClosed.set(false) });
    this.api.deliveryZones(establishmentId).subscribe({ next: (items) => this.zones.set(items) });
    this.api.establishment(establishmentId).subscribe({
      next: (store) => {
        this.loyaltyEnabled.set(store.loyalty_enabled);
        this.loyaltyGoal.set(store.loyalty_goal);
        this.loyaltyReward.set(Number(store.loyalty_reward));
      }
    });
    this.api.products(establishmentId).subscribe({
      // Itens tirados do cardapio somem; os pausados no Local aparecem apagados, para ninguem procurar a toa.
      next: (items) => this.products.set(items.filter((item) => item.is_available))
    });
  }

  /** Categorias que tem algum item, na ordem do cardapio. */
  readonly categoryChips = computed(() => {
    const counts = new Map<string, number>();
    for (const product of this.products()) {
      const id = this.categoryOf(product);
      counts.set(id, (counts.get(id) ?? 0) + 1);
    }
    const chips = this.categories()
      .filter((category) => counts.has(category.id))
      .map((category) => ({ id: category.id, name: category.name, count: counts.get(category.id)! }));
    if (counts.has(NO_CATEGORY)) chips.push({ id: NO_CATEGORY, name: 'Outros', count: counts.get(NO_CATEGORY)! });
    return chips;
  });

  /** Itens agrupados por categoria, filtrados pela busca e pela categoria escolhida. Vendaveis primeiro. */
  readonly sections = computed<ProductSection[]>(() => {
    const term = this.search().trim().toLowerCase();
    const selected = this.selectedCategory();
    const matches = this.products().filter(
      (product) =>
        (selected === null || this.categoryOf(product) === selected) &&
        (!term || product.name.toLowerCase().includes(term) || (product.description ?? '').toLowerCase().includes(term))
    );
    return this.categoryChips()
      .map((chip) => ({
        id: chip.id,
        name: chip.name,
        products: matches
          .filter((product) => this.categoryOf(product) === chip.id)
          .sort((a, b) => Number(!!this.blockReason(a)) - Number(!!this.blockReason(b)))
      }))
      .filter((section) => section.products.length);
  });

  price(product: Product): number {
    return priceFor(product, CHANNEL);
  }

  blockReason(product: Product): string | null {
    return productBlockReason(product, CHANNEL);
  }

  missing(product: Product): string[] {
    return missingIngredients(product, CHANNEL);
  }

  hasCombo(product: Product): boolean {
    return product.option_groups.some((group) => group.depends_on_option_id);
  }

  private categoryOf(product: Product): string {
    const known = this.categories().some((category) => category.id === product.category_id);
    return known ? product.category_id : NO_CATEGORY;
  }

  add(product: Product): void {
    if (this.blockReason(product)) return;
    if (product.option_groups.length) {
      this.customizing.set({ product, line: null });
      return;
    }
    this.addLine(product, { choices: [], notes: '', quantity: 1 });
  }

  editLine(line: CartLine): void {
    this.customizing.set({ product: line.product, line });
  }

  applyCustomization(current: Customizing, item: CustomizedItem): void {
    if (current.line) {
      const updated = this.buildLine(current.product, item, current.line.key);
      this.cart.update((lines) => this.mergeDuplicates(lines.map((line) => (line.key === current.line!.key ? updated : line))));
    } else {
      this.addLine(current.product, item);
    }
    this.customizing.set(null);
  }

  changeQuantity(line: CartLine, delta: number): void {
    this.cart.update((lines) =>
      lines
        .map((item) => (item.key === line.key ? { ...item, quantity: Math.min(99, item.quantity + delta) } : item))
        .filter((item) => item.quantity > 0)
    );
  }

  remove(line: CartLine): void {
    this.cart.update((lines) => lines.filter((item) => item.key !== line.key));
  }

  subtotal(): number {
    return roundCents(this.cart().reduce((total, line) => total + line.unitPrice * line.quantity, 0));
  }

  estimatedTotal(): number {
    const fee = this.form.controls.fulfillment_type.value === 'DELIVERY' ? Number(this.form.controls.delivery_fee.value || 0) : 0;
    return roundCents(this.subtotal() - this.discountTotal() + fee);
  }

  money(value: number | string | null | undefined): number {
    return Number(value ?? 0);
  }

  /** Telefone conhecido: preenche nome, endereco e bairro e mostra a fidelidade. */
  lookupCustomer(): void {
    const establishment = this.tenant.current();
    const phone = this.form.controls.customer_phone.value.trim();
    if (!establishment || phone.replace(/\D/g, '').length < 8) {
      this.customer.set(null);
      this.useReward.set(false);
      return;
    }
    this.api.customerByPhone(establishment.id, phone).subscribe({
      next: (found) => {
        this.customer.set(found);
        this.useReward.set(false);
        if (!found) return;
        const patch: Record<string, string> = {};
        if (!this.form.controls.customer_name.value.trim()) patch['customer_name'] = found.name;
        if (found.address && !this.form.controls.delivery_address.value.trim()) patch['delivery_address'] = found.address;
        const zone = this.activeZones().find((item) => item.name.toLowerCase() === (found.neighborhood ?? '').toLowerCase());
        if (zone && !this.form.controls.delivery_zone_id.value) {
          patch['delivery_zone_id'] = zone.id;
          this.form.controls.delivery_fee.setValue(Number(zone.fee));
        }
        this.form.patchValue(patch);
      }
    });
  }

  applyZoneFee(): void {
    const zone = this.zones().find((item) => item.id === this.form.controls.delivery_zone_id.value);
    if (zone) this.form.controls.delivery_fee.setValue(Number(zone.fee));
  }

  setCoupon(value: string): void {
    this.couponCode.set(value.toUpperCase());
    this.couponApplied.set(false);
    this.couponDiscount.set(0);
    this.couponMessage.set(null);
  }

  checkCoupon(): void {
    const establishment = this.tenant.current();
    const code = this.couponCode().trim();
    if (!establishment || !code) return;
    this.api.checkCoupon(establishment.id, code, this.subtotal()).subscribe({
      next: (result) => {
        this.couponApplied.set(result.valid);
        this.couponDiscount.set(result.valid ? Number(result.discount) : 0);
        this.couponMessage.set(result.message);
      }
    });
  }

  submit(): void {
    const establishment = this.tenant.current();
    if (!establishment || !this.cart().length) return;
    this.loading.set(true);
    const raw = this.form.getRawValue();
    const payload = {
      ...raw,
      delivery_fee: raw.fulfillment_type === 'DELIVERY' ? raw.delivery_fee : 0,
      delivery_address: raw.fulfillment_type === 'DELIVERY' ? raw.delivery_address : null,
      customer_name: raw.customer_name || null,
      customer_phone: raw.customer_phone.trim() || null,
      delivery_zone_id: raw.fulfillment_type === 'DELIVERY' && raw.delivery_zone_id ? raw.delivery_zone_id : null,
      coupon_code: this.couponApplied() ? this.couponCode().trim() : null,
      use_loyalty_reward: this.useReward() && !!this.customer()?.reward_available,
      notes: raw.notes || null,
      items: this.cart().map((line) => ({
        product_id: line.product.id,
        quantity: line.quantity,
        options: line.choices.map((choice) => ({ option_id: choice.optionId, quantity: choice.quantity, notes: choice.notes || null })),
        notes: line.notes || null
      }))
    };
    this.api.createOrder(establishment.id, payload).subscribe({
      next: (order) => {
        this.toast.show('Pedido criado', `${order.order_number} entrou na Central de Pedidos.`, 'success');
        this.cart.set([]);
        this.form.patchValue({ customer_name: '', customer_phone: '', delivery_address: '', delivery_zone_id: '', notes: '' });
        this.customer.set(null);
        this.useReward.set(false);
        this.setCoupon('');
        this.loading.set(false);
      },
      error: (err) => {
        this.toast.show('Erro ao criar pedido', errorMessage(err, 'Revise os dados e tente novamente.'), 'error');
        this.loading.set(false);
      }
    });
  }

  private addLine(product: Product, item: CustomizedItem): void {
    this.cart.update((lines) => this.mergeDuplicates([...lines, this.buildLine(product, item, this.nextKey++)]));
  }

  private buildLine(product: Product, item: CustomizedItem, key: number): CartLine {
    return {
      key,
      product,
      quantity: item.quantity,
      choices: item.choices,
      notes: item.notes,
      unitPrice: roundCents(priceFor(product, CHANNEL) + choicesPrice(product, item.choices)),
      display: this.display(product, item.choices)
    };
  }

  /** Igual ao que a cozinha vai ver, inclusive "Em falta: Sem Alface". */
  private display(product: Product, choices: CartChoice[]): SelectedOption[] {
    const selected = choicesAsSelected(product, choices);
    return [...selected, ...missingAsSelected(product, CHANNEL, selected)];
  }

  /** Dois itens montados do mesmo jeito viram uma linha so, somando a quantidade. */
  private mergeDuplicates(lines: CartLine[]): CartLine[] {
    const merged: CartLine[] = [];
    for (const line of lines) {
      const twin = merged.find((item) => this.signature(item) === this.signature(line));
      if (twin) {
        twin.quantity = Math.min(99, twin.quantity + line.quantity);
      } else {
        merged.push({ ...line });
      }
    }
    return merged;
  }

  private signature(line: CartLine): string {
    const choices = [...line.choices]
      .sort((a, b) => a.optionId.localeCompare(b.optionId))
      .map((choice) => `${choice.optionId}:${choice.quantity}:${choice.notes.trim().toLowerCase()}`);
    return `${line.product.id}|${choices.join(',')}|${line.notes.trim().toLowerCase()}`;
  }
}
