import { Injectable, signal } from '@angular/core';

export interface ToastMessage {
  id: number;
  title: string;
  message: string;
  tone: 'success' | 'error' | 'info';
}

@Injectable({ providedIn: 'root' })
export class ToastService {
  readonly messages = signal<ToastMessage[]>([]);
  private nextId = 1;

  show(title: string, message: string, tone: ToastMessage['tone'] = 'info'): void {
    const toast = { id: this.nextId++, title, message, tone };
    this.messages.update((items) => [toast, ...items].slice(0, 4));
    window.setTimeout(() => this.dismiss(toast.id), 4200);
  }

  dismiss(id: number): void {
    this.messages.update((items) => items.filter((item) => item.id !== id));
  }
}
