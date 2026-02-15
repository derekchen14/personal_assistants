import { writable } from 'svelte/store';

export type LayoutMode = 'split' | 'top' | 'bottom';

export const layoutMode = writable<LayoutMode>('split');
export const loading = writable(false);
