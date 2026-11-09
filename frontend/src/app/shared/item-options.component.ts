import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import { SelectedOption } from '../core/models';
import { groupSelectedOptions } from './order-options';

/** Escolhas de um item agrupadas: "Bebida: Coca-Cola", "Retirar: Sem alface", "Sabores: 1/2 Calabresa (sem cebola)". */
@Component({
  selector: 'app-item-options',
  standalone: true,
  template: `
    @for (group of groups(); track $index) {
      <p [class]="lineClass()">
        @if (group.name) {
          <span class="font-bold">{{ group.name }}:</span>
        } @else {
          <span>+</span>
        }
        @for (entry of group.entries; track $index) {
          <span [class]="entry.removal && highlight() ? 'font-extrabold text-red-700' : ''"> {{ entry.label }}</span>
          @if (entry.notes) {
            <span [class]="highlight() ? 'font-extrabold text-amber-800' : 'font-semibold'"> ({{ entry.notes }})</span>
          }
          @if (!$last) {<span>,</span>}
        }
      </p>
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class ItemOptionsComponent {
  readonly options = input<SelectedOption[] | null | undefined>([]);
  /** sm: drawer/carrinho, lg: tela da cozinha, ticket: comanda impressa */
  readonly size = input<'sm' | 'lg' | 'ticket'>('sm');
  /** Destaca "Sem ..." e observacoes (cozinha) */
  readonly highlight = input(false);

  readonly groups = computed(() => groupSelectedOptions(this.options()));
  readonly lineClass = computed(() => {
    if (this.size() === 'lg') return 'mt-1 text-base font-semibold text-zinc-700';
    if (this.size() === 'ticket') return 'text-xs';
    return 'text-sm text-zinc-500';
  });
}
