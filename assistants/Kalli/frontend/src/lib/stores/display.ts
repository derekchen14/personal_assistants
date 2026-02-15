import { writable } from 'svelte/store';

export interface FrameData {
    type: string;
    show: boolean;
    data: Record<string, unknown>;
    source?: string;
    display_name?: string;
}

export const activeFrame = writable<FrameData | null>(null);
