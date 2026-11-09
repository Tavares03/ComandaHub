import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, effect, inject, signal, untracked } from '@angular/core';
import { FormBuilder, FormsModule, ReactiveFormsModule, Validators } from '@angular/forms';
import { LucideAngularModule } from 'lucide-angular';

import { ApiService } from '../../core/api.service';
import { AvailabilityResponse, Category, Ingredient, IngredientUnit, Product, ProductInput, SalesChannel } from '../../core/models';
import { TenantService } from '../../core/tenant.service';
import { ToastService } from '../../core/toast.service';
import { CHANNELS, errorMessage, marginPercent, missingIngredients, priceFor, productBlockReason } from '../../shared/order-options';
import { AvailabilityDialogComponent, AvailabilityTarget } from './availability-dialog.component';
import { IngredientsPanelComponent, formatQty } from './ingredients-panel.component';
import { EditableGroup, OptionGroupsEditorComponent, groupProblems, toEditableGroups, toGroupInputs } from './option-groups-editor.component';

interface FormIngredient {
  ingredient_id: string;
  name: string;
  unit: IngredientUnit;
  essential: boolean;
  quantity: number | null;
}

interface ChannelStatus {
  id: SalesChannel;
  short: string;
  state: 'ok' | 'paused' | 'without';
  detail: string;
}

interface AvailabilityDialogState {
  target: AvailabilityTarget;
  action: 'pause' | 'resume';
  paused: SalesChannel[];
  usedBy: Product[];
}

@Component({
  selector: 'app-products',
  standalone: true,
  imports: [CommonModule, FormsModule, ReactiveFormsModule, LucideAngularModule, OptionGroupsEditorComponent, AvailabilityDialogComponent, IngredientsPanelComponent],
  template: `
    <section class="grid gap-5 xl:grid-cols-[1fr_380px]">
      <div class="min-w-0 space-y-5">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 class="text-2xl font-extrabold tracking-normal text-zinc-950">Cardapio</h1>
            <p class="mt-1 text-sm text-zinc-500">Itens, ingredientes, estoque e o que esta pausado no iFood, no 99 e na loja.</p>
          </div>
          <div class="flex flex-wrap gap-2">
            <button class="focus-ring inline-flex h-10 items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 text-sm font-bold hover:bg-zinc-50" (click)="bulk.set({ channel: 'IFOOD', percent: 20, round: true })">
              <i-lucide name="banknote" [size]="16" /> Preco por canal
            </button>
            <button class="focus-ring inline-flex h-10 items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 text-sm font-bold hover:bg-zinc-50" (click)="addCategory()">
              <i-lucide name="tag" [size]="16" /> Nova categoria
            </button>
          </div>
        </div>

        <div class="inline-flex rounded-lg border border-zinc-200 bg-white p-1" role="tablist">
          <button type="button" role="tab" class="focus-ring rounded-md px-4 py-1.5 text-sm font-bold"
                  [attr.aria-selected]="tab() === 'items'"
                  [ngClass]="tab() === 'items' ? 'bg-zinc-900 text-white' : 'text-zinc-600 hover:bg-zinc-50'" (click)="tab.set('items')">
            Itens <span class="ml-1 opacity-70">{{ products().length }}</span>
          </button>
          <button type="button" role="tab" class="focus-ring rounded-md px-4 py-1.5 text-sm font-bold"
                  [attr.aria-selected]="tab() === 'ingredients'"
                  [ngClass]="tab() === 'ingredients' ? 'bg-zinc-900 text-white' : 'text-zinc-600 hover:bg-zinc-50'" (click)="tab.set('ingredients')">
            Ingredientes e estoque <span class="ml-1 opacity-70">{{ ingredients().length }}</span>
            @if (stockAlerts()) { <span class="ml-1 rounded-full bg-amber-400 px-1.5 text-xs text-zinc-950">{{ stockAlerts() }}</span> }
          </button>
        </div>

        @if (tab() === 'items') {
          <div class="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1 sm:flex-wrap sm:overflow-visible" aria-label="Filtrar por categoria">
            <button type="button" class="focus-ring shrink-0 rounded-full border px-3.5 py-1.5 text-sm font-bold"
                    [ngClass]="categoryFilter() === null ? 'border-brand-500 bg-brand-500 text-white' : 'border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50'"
                    (click)="categoryFilter.set(null)">Todos</button>
            @for (category of categories(); track category.id) {
              <button type="button" class="focus-ring shrink-0 rounded-full border px-3.5 py-1.5 text-sm font-bold"
                      [ngClass]="categoryFilter() === category.id ? 'border-brand-500 bg-brand-500 text-white' : 'border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50'"
                      (click)="categoryFilter.set(category.id)">{{ category.name }}</button>
            }
          </div>

          <div class="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
            @for (product of visibleProducts(); track product.id) {
              <article class="app-card overflow-hidden" [class.opacity-60]="!product.is_available">
                <div class="h-28 bg-zinc-200">
                  @if (product.image_url) {
                    <img class="h-full w-full object-cover" [src]="product.image_url" [alt]="product.name" />
                  }
                </div>
                <div class="p-4">
                  <div class="flex items-start justify-between gap-3">
                    <div>
                      <p class="font-extrabold text-zinc-950">{{ product.name }}</p>
                      <p class="mt-1 text-xs font-bold uppercase text-zinc-400">{{ product.category?.name || 'Sem categoria' }}</p>
                    </div>
                    <p class="whitespace-nowrap text-lg font-extrabold">{{ product.price | currency:'BRL':'symbol':'1.2-2' }}</p>
                  </div>

                  @if (cost(product) > 0) {
                    <p class="mt-1 text-xs font-semibold text-zinc-500" [title]="'Custo da ficha tecnica: ' + ingredientNames(product)">
                      Custo {{ cost(product) | currency:'BRL':'symbol':'1.2-2' }} - margem
                      <span [ngClass]="margin(product, 'LOCAL') < 50 ? 'text-amber-700' : 'text-emerald-700'">{{ margin(product, 'LOCAL') }}%</span>
                    </p>
                  }

                  @if (product.is_available) {
                    <div class="mt-3 flex flex-wrap gap-1.5">
                      @for (status of channelStatus(product); track status.id) {
                        <span class="inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-bold" [title]="status.detail"
                              [ngClass]="status.state === 'ok' ? 'bg-emerald-50 text-emerald-700' : status.state === 'paused' ? 'bg-red-50 text-red-700' : 'bg-amber-50 text-amber-800'">
                          @if (status.state === 'paused') { <i-lucide name="circle-pause" [size]="12" /> }
                          @if (status.state === 'without') { <i-lucide name="triangle-alert" [size]="12" /> }
                          {{ status.short }}
                          @if (hasChannelPrice(product, status.id)) { {{ channelPrice(product, status.id) | currency:'BRL':'symbol':'1.2-2' }} }
                          {{ status.state === 'without' ? '(' + status.detail + ')' : '' }}
                        </span>
                      }
                    </div>
                  } @else {
                    <p class="mt-3 inline-flex rounded-full bg-zinc-100 px-2 py-1 text-xs font-bold text-zinc-600">Fora do cardapio</p>
                  }

                  <div class="mt-3 flex flex-wrap gap-1.5 text-xs text-zinc-500">
                    @if (product.option_groups.length) {
                      <span class="inline-flex items-center gap-1 rounded-full bg-zinc-100 px-2 py-1 font-bold text-zinc-700" [title]="groupNames(product)">
                        <i-lucide name="sliders-horizontal" [size]="12" /> {{ product.option_groups.length }} grupo(s)
                      </span>
                    }
                    @if (hasCombo(product)) {
                      <span class="inline-flex items-center gap-1 rounded-full bg-brand-50 px-2 py-1 font-bold text-brand-700">
                        <i-lucide name="shopping-bag" [size]="12" /> Vira combo
                      </span>
                    }
                    @if (product.ingredients.length) {
                      <span class="inline-flex items-center gap-1 rounded-full bg-zinc-100 px-2 py-1 font-bold text-zinc-700" [title]="ingredientNames(product)">
                        <i-lucide name="carrot" [size]="12" /> {{ product.ingredients.length }} ingrediente(s)
                      </span>
                    }
                  </div>

                  <div class="mt-4 flex gap-2">
                    <button class="focus-ring inline-flex h-9 flex-1 items-center justify-center gap-1.5 rounded-lg border border-zinc-200 text-sm font-bold hover:bg-zinc-50" (click)="edit(product)">
                      <i-lucide name="edit-3" [size]="15" /> Editar
                    </button>
                    @if (product.is_available) {
                      <button class="focus-ring inline-flex h-9 flex-1 items-center justify-center gap-1.5 rounded-lg border border-red-200 text-sm font-bold text-red-700 hover:bg-red-50"
                              (click)="openProductAvailability(product, 'pause')">
                        <i-lucide name="circle-pause" [size]="15" /> Pausar
                      </button>
                      @if (product.paused_channels.length) {
                        <button class="focus-ring inline-flex h-9 flex-1 items-center justify-center gap-1.5 rounded-lg border border-emerald-200 text-sm font-bold text-emerald-700 hover:bg-emerald-50"
                                (click)="openProductAvailability(product, 'resume')">
                          <i-lucide name="circle-play" [size]="15" /> Reativar
                        </button>
                      }
                      <button class="focus-ring h-9 rounded-lg border border-zinc-200 px-3 text-zinc-600 hover:bg-zinc-50" (click)="archive(product)"
                              title="Tirar do cardapio (todas as vendas)" aria-label="Tirar do cardapio">
                        <i-lucide name="archive" [size]="15" />
                      </button>
                    } @else {
                      <button class="focus-ring inline-flex h-9 flex-1 items-center justify-center gap-1.5 rounded-lg border border-emerald-200 text-sm font-bold text-emerald-700 hover:bg-emerald-50"
                              (click)="restore(product)">
                        <i-lucide name="archive-restore" [size]="15" /> Voltar ao cardapio
                      </button>
                    }
                  </div>
                </div>
              </article>
            } @empty {
              <div class="app-card p-8 text-center text-sm text-zinc-500">Nenhum produto nesta categoria.</div>
            }
          </div>
        } @else {
          <app-ingredients-panel class="block" [ingredients]="ingredients()" [products]="products()" [multiStore]="multiStore()" (changed)="reload()" />
        }
      </div>

      <aside class="app-card h-max p-5 xl:sticky xl:top-20 xl:max-h-[calc(100vh-6rem)] xl:overflow-y-auto">
        <h2 class="text-lg font-extrabold text-zinc-950">{{ editingId() ? 'Editar produto' : 'Novo produto' }}</h2>
        <form class="mt-4 space-y-4" [formGroup]="form" (ngSubmit)="save()">
          <label class="block">
            <span class="mb-1 block text-xs font-bold text-zinc-500">Nome</span>
            <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" formControlName="name" />
          </label>
          <label class="block">
            <span class="mb-1 block text-xs font-bold text-zinc-500">Categoria</span>
            <select class="focus-ring h-10 w-full rounded-lg border border-zinc-200 bg-white px-3 text-sm" formControlName="category_id">
              @for (category of categories(); track category.id) {
                <option [value]="category.id">{{ category.name }}</option>
              }
            </select>
          </label>
          <label class="block">
            <span class="mb-1 block text-xs font-bold text-zinc-500">Descricao</span>
            <textarea class="focus-ring min-h-20 w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm" formControlName="description"></textarea>
          </label>
          <label class="block">
            <span class="mb-1 block text-xs font-bold text-zinc-500">Preco</span>
            <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" type="number" step="0.01" formControlName="price" />
          </label>
          <label class="block">
            <span class="mb-1 block text-xs font-bold text-zinc-500">Imagem opcional</span>
            <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" formControlName="image_url" />
          </label>
          <label class="flex items-center gap-2 text-sm font-bold text-zinc-700">
            <input type="checkbox" formControlName="is_available" />
            No cardapio
          </label>
        </form>

        <div class="mt-5 space-y-2 border-t border-zinc-100 pt-4">
          <div>
            <h3 class="text-sm font-extrabold text-zinc-950">Preco por canal</h3>
            <p class="text-xs text-zinc-500">Deixe vazio para usar o preco normal. Ex.: mais caro no iFood por causa da comissao.</p>
          </div>
          <div class="grid grid-cols-3 gap-2">
            @for (channel of channels; track channel.id) {
              <label class="block">
                <span class="mb-1 block text-xs font-bold text-zinc-500">{{ channel.short }}</span>
                <input class="focus-ring h-9 w-full rounded-md border border-zinc-200 px-2 text-sm" type="number" step="0.01" min="0"
                       [placeholder]="form.controls.price.value" [ngModel]="formPrices()[channel.id]" (ngModelChange)="setFormPrice(channel.id, $event)"
                       [attr.aria-label]="'Preco no ' + channel.short" />
              </label>
            }
          </div>
        </div>

        <div class="mt-5 space-y-2 border-t border-zinc-100 pt-4">
          <div class="flex items-start justify-between gap-2">
            <div>
              <h3 class="text-sm font-extrabold text-zinc-950">Ingredientes (ficha tecnica)</h3>
              <p class="text-xs text-zinc-500">Quanto vai em 1 item: da baixa no estoque e calcula o custo. "Principal": sem ele o item nao sai.</p>
            </div>
            @if (formCost() > 0) {
              <span class="shrink-0 rounded-full bg-zinc-100 px-2 py-1 text-xs font-bold text-zinc-700">Custo {{ formCost() | currency:'BRL':'symbol':'1.2-2' }}</span>
            }
          </div>
          @for (item of formIngredients(); track item.ingredient_id) {
            <div class="grid grid-cols-[1fr_86px_auto_auto] items-center gap-2 rounded-md bg-zinc-50 px-2.5 py-1.5">
              <span class="truncate text-sm font-bold text-zinc-800">{{ item.name }}</span>
              <label class="flex items-center gap-1">
                <input class="focus-ring h-8 w-full min-w-0 rounded-md border border-zinc-200 bg-white px-1.5 text-sm" type="number" step="0.001" min="0" placeholder="0"
                       [ngModel]="item.quantity" (ngModelChange)="setIngredientQty(item, $event)" [attr.aria-label]="'Quantidade de ' + item.name" />
                <span class="text-xs text-zinc-500">{{ item.unit }}</span>
              </label>
              <label class="flex items-center gap-1 text-xs font-bold text-zinc-600" title="Sem ele o item sai do cardapio">
                <input type="checkbox" [checked]="item.essential" (change)="toggleEssential(item)" /> Princ.
              </label>
              <button type="button" class="focus-ring rounded p-1 text-red-600 hover:bg-red-50" (click)="removeFormIngredient(item)" [attr.aria-label]="'Tirar ' + item.name">
                <i-lucide name="x" [size]="14" />
              </button>
            </div>
          }
          <div class="flex gap-2">
            <input class="focus-ring h-9 min-w-0 flex-1 rounded-md border border-zinc-200 px-2.5 text-sm" list="ingredient-options" placeholder="Adicionar ingrediente"
                   [ngModel]="ingredientDraft()" (ngModelChange)="ingredientDraft.set($event)" (keydown.enter)="$event.preventDefault(); addFormIngredient()" />
            <datalist id="ingredient-options">
              @for (ingredient of ingredients(); track ingredient.id) {
                <option [value]="ingredient.name"></option>
              }
            </datalist>
            <button type="button" class="focus-ring rounded-md border border-zinc-200 px-3 text-sm font-bold hover:bg-zinc-50 disabled:opacity-40"
                    [disabled]="ingredientDraft().trim().length < 2" (click)="addFormIngredient()" aria-label="Adicionar ingrediente">
              <i-lucide name="plus" [size]="15" />
            </button>
          </div>
        </div>

        <div class="mt-5 border-t border-zinc-100 pt-4">
          <app-option-groups-editor [(groups)]="groups" [copySources]="copySources()" [linkProducts]="linkProducts()" [ingredients]="ingredients()" />
        </div>

        <div class="mt-5 flex gap-2">
          <button class="focus-ring inline-flex h-10 flex-1 items-center justify-center gap-2 rounded-lg bg-brand-500 text-sm font-extrabold text-white hover:bg-brand-600 disabled:opacity-50" [disabled]="form.invalid || loading()" type="button" (click)="save()">
            <i-lucide name="save" [size]="16" /> Salvar
          </button>
          @if (editingId()) {
            <button class="h-10 rounded-lg border border-zinc-200 px-3 text-sm font-bold" type="button" (click)="resetForm()">Cancelar</button>
          }
        </div>
      </aside>
    </section>

    @if (availability(); as dialog) {
      <app-availability-dialog
        [target]="dialog.target"
        [action]="dialog.action"
        [pausedChannels]="dialog.paused"
        [usedBy]="dialog.usedBy"
        [multiStore]="multiStore()"
        (done)="availabilityDone(dialog, $event)"
        (closed)="availability.set(null)"
      />
    }

    @if (bulk(); as current) {
      <div class="fixed inset-0 z-50 bg-zinc-950/40" (click)="bulk.set(null)"></div>
      <section class="fixed inset-x-0 bottom-0 z-50 rounded-t-2xl bg-white p-5 shadow-2xl sm:inset-auto sm:left-1/2 sm:top-1/2 sm:w-[460px] sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-2xl"
               role="dialog" aria-modal="true" aria-label="Preco por canal">
        <div class="flex items-start justify-between gap-3">
          <div>
            <p class="text-xs font-bold uppercase text-brand-600">Ajuste em lote</p>
            <h2 class="text-xl font-extrabold text-zinc-950">Preco por canal</h2>
            <p class="text-sm text-zinc-500">Preco do canal = preco normal + percentual.</p>
          </div>
          <button type="button" class="focus-ring rounded-md border border-zinc-200 p-2" (click)="bulk.set(null)" aria-label="Fechar">
            <i-lucide name="x" [size]="18" />
          </button>
        </div>
        <div class="mt-4 space-y-3">
          <label class="block">
            <span class="mb-1 block text-xs font-bold text-zinc-500">Canal</span>
            <select class="focus-ring h-10 w-full rounded-lg border border-zinc-200 bg-white px-2 text-sm" [ngModel]="current.channel" (ngModelChange)="bulk.set({ channel: $event, percent: current.percent, round: current.round })">
              @for (channel of channels; track channel.id) { <option [ngValue]="channel.id">{{ channel.label }}</option> }
            </select>
          </label>
          <label class="block">
            <span class="mb-1 block text-xs font-bold text-zinc-500">Acrescimo (%)</span>
            <input class="focus-ring h-10 w-full rounded-lg border border-zinc-200 px-3 text-sm" type="number" step="1"
                   [ngModel]="current.percent" (ngModelChange)="bulk.set({ channel: current.channel, percent: $event, round: current.round })" />
          </label>
          <label class="flex items-center gap-2 text-sm font-bold text-zinc-700">
            <input type="checkbox" [ngModel]="current.round" (ngModelChange)="bulk.set({ channel: current.channel, percent: current.percent, round: $event })" />
            Arredondar para cima ate ,90 (ex.: 36,00 vira 36,90)
          </label>
          <p class="rounded-lg bg-zinc-50 p-3 text-xs text-zinc-600">
            Vale para {{ bulkTargets().length }} item(ns){{ categoryFilter() ? ' da categoria filtrada' : '' }}.
            Ex.: {{ bulkExample(current) }}
          </p>
        </div>
        <div class="mt-5 flex flex-wrap gap-2">
          <button type="button" class="focus-ring h-11 rounded-lg border border-red-200 px-4 text-sm font-bold text-red-700 hover:bg-red-50" (click)="applyBulk(current.channel, null, false)">
            Usar preco normal
          </button>
          <button type="button" class="focus-ring inline-flex h-11 flex-1 items-center justify-center gap-2 rounded-lg bg-brand-500 text-sm font-extrabold text-white hover:bg-brand-600"
                  (click)="applyBulk(current.channel, current.percent, current.round)">
            <i-lucide name="save" [size]="16" /> Aplicar
          </button>
        </div>
      </section>
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class ProductsComponent {
  private readonly api = inject(ApiService);
  private readonly tenant = inject(TenantService);
  private readonly toast = inject(ToastService);
  private readonly fb = inject(FormBuilder);

  readonly channels = CHANNELS;
  readonly tab = signal<'items' | 'ingredients'>('items');
  readonly categories = signal<Category[]>([]);
  readonly categoryFilter = signal<string | null>(null);
  readonly products = signal<Product[]>([]);
  readonly ingredients = signal<Ingredient[]>([]);
  readonly editingId = signal<string | null>(null);
  readonly loading = signal(false);
  readonly groups = signal<EditableGroup[]>([]);
  readonly formIngredients = signal<FormIngredient[]>([]);
  readonly formPrices = signal<Partial<Record<SalesChannel, number | null>>>({});
  readonly ingredientDraft = signal('');
  readonly availability = signal<AvailabilityDialogState | null>(null);
  readonly bulk = signal<{ channel: SalesChannel; percent: number | null; round: boolean } | null>(null);
  readonly form = this.fb.nonNullable.group({
    name: ['', [Validators.required, Validators.minLength(2)]],
    category_id: ['', Validators.required],
    description: [''],
    price: [1, [Validators.required, Validators.min(0.01)]],
    image_url: [''],
    is_available: [true]
  });

  constructor() {
    effect(() => {
      const establishment = this.tenant.current();
      if (establishment) {
        // So a troca de loja dispara isto; o resto e lido sem criar dependencia
        untracked(() => {
          this.categoryFilter.set(null);
          this.resetForm();
          this.load(establishment.id);
        });
      }
    }, { allowSignalWrites: true });
  }

  load(establishmentId: string): void {
    this.api.categories(establishmentId).subscribe({
      next: (items) => {
        this.categories.set(items);
        if (!this.form.controls.category_id.value && items[0]) {
          this.form.controls.category_id.setValue(items[0].id);
        }
      }
    });
    this.api.products(establishmentId).subscribe({ next: (items) => this.products.set(items) });
    this.api.ingredients(establishmentId).subscribe({ next: (items) => this.ingredients.set(items) });
  }

  reload(): void {
    const establishment = this.tenant.current();
    if (establishment) this.load(establishment.id);
  }

  readonly visibleProducts = computed(() => {
    const filter = this.categoryFilter();
    return filter ? this.products().filter((product) => product.category_id === filter) : this.products();
  });

  readonly copySources = computed(() =>
    this.products().filter((product) => product.id !== this.editingId() && product.option_groups.length > 0)
  );

  /** Produtos que uma opcao pode representar (nao pode ser o proprio item) */
  readonly linkProducts = computed(() => this.products().filter((product) => product.id !== this.editingId()));

  /** "Todas as minhas lojas" so aparece para quem edita mais de uma loja */
  readonly multiStore = computed(() => this.tenant.establishments().filter((item) => item.role !== 'KITCHEN').length > 1);

  /** Ingredientes zerados ou abaixo do minimo (badge na aba) */
  readonly stockAlerts = computed(
    () =>
      this.ingredients().filter((item) => {
        if (item.stock_quantity === null) return false;
        const stock = Number(item.stock_quantity);
        return stock <= 0 || (item.min_stock !== null && stock <= Number(item.min_stock));
      }).length
  );

  /** Custo da ficha tecnica do formulario (para ver antes de salvar) */
  readonly formCost = computed(() =>
    this.formIngredients().reduce((sum, item) => {
      const ingredient = this.ingredients().find((entry) => entry.id === item.ingredient_id);
      return sum + (Number(item.quantity) || 0) * Number(ingredient?.cost_per_unit ?? 0);
    }, 0)
  );

  readonly bulkTargets = computed(() => this.visibleProducts());

  channelStatus(product: Product): ChannelStatus[] {
    return CHANNELS.map((channel) => {
      const blocked = productBlockReason(product, channel.id);
      if (blocked) return { id: channel.id, short: channel.short, state: 'paused', detail: blocked };
      const missing = missingIngredients(product, channel.id);
      if (missing.length) return { id: channel.id, short: channel.short, state: 'without', detail: `sem ${missing.join(', ')}` };
      return { id: channel.id, short: channel.short, state: 'ok', detail: 'Vendendo' };
    });
  }

  cost(product: Product): number {
    return Number(product.unit_cost ?? 0);
  }

  margin(product: Product, channel: SalesChannel): number {
    return marginPercent(priceFor(product, channel), this.cost(product));
  }

  hasChannelPrice(product: Product, channel: SalesChannel): boolean {
    const value = product.channel_prices?.[channel];
    return value !== undefined && value !== null;
  }

  channelPrice(product: Product, channel: SalesChannel): number {
    return priceFor(product, channel);
  }

  hasCombo(product: Product): boolean {
    return product.option_groups.some((group) => group.depends_on_option_id);
  }

  groupNames(product: Product): string {
    return product.option_groups.map((group) => group.name).join(', ');
  }

  ingredientNames(product: Product): string {
    return product.ingredients
      .map((item) => `${item.name}${Number(item.quantity) ? ' ' + formatQty(item.quantity) + ' ' + item.unit : ''}${item.essential ? ' (principal)' : ''}`)
      .join(', ');
  }

  // ---------------------------------------------------------------- pausar / reativar

  openProductAvailability(product: Product, action: 'pause' | 'resume'): void {
    this.availability.set({
      target: { type: 'product', id: product.id, name: product.name },
      action,
      paused: product.paused_channels,
      usedBy: []
    });
  }

  availabilityDone(dialog: AvailabilityDialogState, result: AvailabilityResponse): void {
    const changed = result.results.reduce((sum, store) => sum + store.changes.length, 0);
    const stores = result.results.length > 1 ? ` em ${result.results.length} lojas` : '';
    const verb = dialog.action === 'pause' ? 'Pausado' : 'Reativado';
    this.toast.show(`${verb}: ${dialog.target.name}`, `${changed} lugar(es) atualizado(s)${stores}.`, 'success');
    this.availability.set(null);
    this.reload();
  }

  archive(product: Product): void {
    const establishment = this.tenant.current();
    if (!establishment || !window.confirm(`Tirar ${product.name} do cardapio em todos os canais? (Para so pausar em um canal, use "Pausar".)`)) return;
    this.api.deleteProduct(establishment.id, product.id).subscribe({
      next: (updated) => this.replaceProduct(updated),
      error: () => this.toast.show('Erro', 'Nao foi possivel tirar o produto do cardapio.', 'error')
    });
  }

  restore(product: Product): void {
    const establishment = this.tenant.current();
    if (!establishment) return;
    this.api.updateProduct(establishment.id, product.id, { is_available: true }).subscribe({
      next: (updated) => this.replaceProduct(updated)
    });
  }

  // ---------------------------------------------------------------- preco por canal em lote

  bulkExample(current: { channel: SalesChannel; percent: number | null; round: boolean }): string {
    const sample = this.bulkTargets()[0];
    if (!sample || current.percent === null || (current.percent as unknown) === '') return 'informe o percentual';
    let value = Math.round(Number(sample.price) * (1 + Number(current.percent) / 100) * 100) / 100;
    if (current.round) {
      const whole = Math.floor(value);
      value = whole + 0.9 >= value ? whole + 0.9 : whole + 1.9;
    }
    const fmt = (n: number) => n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    return `${sample.name}: ${fmt(Number(sample.price))} vira ${fmt(value)}`;
  }

  applyBulk(channel: SalesChannel, percent: number | null, round: boolean): void {
    const establishment = this.tenant.current();
    if (!establishment) return;
    const ids = this.bulkTargets().map((product) => product.id);
    const value = percent === null || (percent as unknown) === '' ? null : Number(percent);
    this.api.bulkChannelPrices(establishment.id, { channel, percent: value, round_to_90: round, product_ids: ids }).subscribe({
      next: () => {
        const label = CHANNELS.find((item) => item.id === channel)?.short ?? channel;
        this.toast.show('Precos atualizados', value === null ? `${label} volta ao preco normal.` : `${label}: +${value}% em ${ids.length} item(ns).`, 'success');
        this.bulk.set(null);
        this.reload();
      },
      error: (err) => this.toast.show('Erro', errorMessage(err, 'Nao foi possivel atualizar os precos.'), 'error')
    });
  }

  // ---------------------------------------------------------------- formulario

  setFormPrice(channel: SalesChannel, value: number | string | null): void {
    this.formPrices.update((prices) => ({ ...prices, [channel]: value === '' || value === null ? null : Number(value) }));
  }

  /** Usa o ingrediente com esse nome; se nao existir, cadastra na hora. */
  addFormIngredient(): void {
    const establishment = this.tenant.current();
    const name = this.ingredientDraft().trim();
    if (!establishment || name.length < 2) return;
    const existing = this.ingredients().find((item) => item.name.trim().toLowerCase() === name.toLowerCase());
    if (existing) {
      this.pushFormIngredient(existing);
      return;
    }
    this.api.createIngredient(establishment.id, { name }).subscribe({
      next: (ingredient) => {
        this.ingredients.update((items) => [...items, ingredient].sort((a, b) => a.name.localeCompare(b.name)));
        this.pushFormIngredient(ingredient);
      },
      error: (err) => this.toast.show('Erro', errorMessage(err, 'Nao foi possivel criar o ingrediente.'), 'error')
    });
  }

  setIngredientQty(item: FormIngredient, value: number | string | null): void {
    this.formIngredients.update((items) =>
      items.map((entry) => (entry === item ? { ...entry, quantity: value === '' || value === null ? null : Number(value) } : entry))
    );
  }

  toggleEssential(item: FormIngredient): void {
    this.formIngredients.update((items) => items.map((entry) => (entry === item ? { ...entry, essential: !entry.essential } : entry)));
  }

  removeFormIngredient(item: FormIngredient): void {
    this.formIngredients.update((items) => items.filter((entry) => entry !== item));
  }

  private pushFormIngredient(ingredient: Ingredient): void {
    if (!this.formIngredients().some((item) => item.ingredient_id === ingredient.id)) {
      this.formIngredients.update((items) => [
        ...items,
        { ingredient_id: ingredient.id, name: ingredient.name, unit: ingredient.unit, essential: false, quantity: null }
      ]);
    }
    this.ingredientDraft.set('');
  }

  edit(product: Product): void {
    this.editingId.set(product.id);
    this.form.patchValue({
      name: product.name,
      category_id: product.category_id,
      description: product.description ?? '',
      price: Number(product.price),
      image_url: product.image_url ?? '',
      is_available: product.is_available
    });
    this.groups.set(toEditableGroups(product.option_groups));
    this.formIngredients.set(
      product.ingredients.map(({ ingredient_id, name, essential, quantity, unit }) => ({
        ingredient_id,
        name,
        unit,
        essential,
        quantity: Number(quantity) || null
      }))
    );
    const prices: Partial<Record<SalesChannel, number | null>> = {};
    for (const channel of CHANNELS) {
      const value = product.channel_prices?.[channel.id];
      prices[channel.id] = value === undefined || value === null ? null : Number(value);
    }
    this.formPrices.set(prices);
  }

  save(): void {
    const establishment = this.tenant.current();
    if (!establishment || this.form.invalid) return;
    const invalid = this.groups().filter((group) => groupProblems(group, this.groups()).length);
    if (invalid.length) {
      invalid.forEach((group) => (group.open = true));
      this.groups.set([...this.groups()]);
      this.toast.show('Revise a personalizacao', `Corrija o grupo "${invalid[0].name || 'sem nome'}" antes de salvar.`, 'error');
      return;
    }
    this.loading.set(true);
    const raw = this.form.getRawValue();
    const channelPrices: Partial<Record<SalesChannel, number>> = {};
    for (const [channel, value] of Object.entries(this.formPrices()) as Array<[SalesChannel, number | null]>) {
      if (value !== null && value !== undefined && value > 0) channelPrices[channel] = value;
    }
    const payload: ProductInput = {
      ...raw,
      image_url: raw.image_url || null,
      option_groups: toGroupInputs(this.groups()),
      ingredients: this.formIngredients().map(({ ingredient_id, essential, quantity }) => ({ ingredient_id, essential, quantity: Number(quantity) || 0 })),
      channel_prices: channelPrices
    };
    const request = this.editingId()
      ? this.api.updateProduct(establishment.id, this.editingId()!, payload)
      : this.api.createProduct(establishment.id, payload);
    request.subscribe({
      next: () => {
        this.toast.show('Cardapio salvo', 'Produto atualizado com sucesso.', 'success');
        this.resetForm();
        this.load(establishment.id);
        this.loading.set(false);
      },
      error: (err) => {
        this.toast.show('Erro no cardapio', errorMessage(err, 'Nao foi possivel salvar.'), 'error');
        this.loading.set(false);
      }
    });
  }

  addCategory(): void {
    const establishment = this.tenant.current();
    if (!establishment) return;
    const name = window.prompt('Nome da categoria');
    if (!name) return;
    this.api.createCategory(establishment.id, { name, sort_order: this.categories().length + 1 }).subscribe({
      next: (category) => {
        this.categories.update((items) => [...items, category]);
        this.form.controls.category_id.setValue(category.id);
      },
      error: () => this.toast.show('Erro', 'Nao foi possivel criar a categoria.', 'error')
    });
  }

  resetForm(): void {
    this.editingId.set(null);
    this.groups.set([]);
    this.formIngredients.set([]);
    this.formPrices.set({});
    this.ingredientDraft.set('');
    this.form.reset({
      name: '',
      category_id: this.categories()[0]?.id ?? '',
      description: '',
      price: 1,
      image_url: '',
      is_available: true
    });
  }

  private replaceProduct(updated: Product): void {
    this.products.update((items) => items.map((item) => (item.id === updated.id ? updated : item)));
  }
}
