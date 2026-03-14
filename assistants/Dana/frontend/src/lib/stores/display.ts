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
export type ActivePage = 'sheets' | 'queries';

export const activeFrame = writable<FrameData | null>(null);
export const topFrame = writable<FrameData | null>(null);
export const bottomFrame = writable<FrameData | null>(null);
export const activePage = writable<ActivePage>('sheets');

const _expanded = writable(false);

export const displayLayout = derived(
    [topFrame, bottomFrame, _expanded],
    ([$top, $bottom, $exp]) => {
        if ($exp && $bottom) return 'bottom' as DisplayLayout;
        if ($top && $bottom) return 'split' as DisplayLayout;
        if ($top) return 'top' as DisplayLayout;
        return 'bottom' as DisplayLayout;
    },
);

export function clearFrames() {
    activeFrame.set(null);
    topFrame.set(null);
    bottomFrame.set(null);
    _expanded.set(false);
}

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

export function expandPost() {
    _expanded.set(true);
}

export function collapsePost() {
    _expanded.set(false);
}
