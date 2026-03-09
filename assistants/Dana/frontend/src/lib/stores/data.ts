import { writable } from 'svelte/store';

export const activeData = writable<Record<string, unknown> | null>(null);
