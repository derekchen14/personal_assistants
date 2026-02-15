import { writable, derived } from 'svelte/store';

export interface FrameData {
    type: string;
    show: boolean;
    data: Record<string, unknown>;
    source?: string;
    display_name?: string;
    panel?: 'top' | 'bottom';
}

export type DisplayLayout = 'top' | 'split' | 'bottom';

export const activeFrame = writable<FrameData | null>(null);
export const topFrame = writable<FrameData | null>(null);
export const bottomFrame = writable<FrameData | null>(null);

export const displayLayout = derived(
    [topFrame, bottomFrame],
    ([$top, $bottom]) => {
        if ($top && $bottom) return 'split' as DisplayLayout;
        if ($top) return 'top' as DisplayLayout;
        return 'bottom' as DisplayLayout;
    },
);

export function setFrame(frame: FrameData) {
    console.log('[display] setFrame type=%s panel=%s show=%s', frame.type, frame.panel, frame.show);
    activeFrame.set(frame);
    const panel = frame.panel || 'bottom';
    if (panel === 'top') {
        topFrame.set(frame);
    } else {
        bottomFrame.set(frame);
    }
}
