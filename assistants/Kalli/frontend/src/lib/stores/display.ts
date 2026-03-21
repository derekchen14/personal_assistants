import { writable, derived, get } from 'svelte/store';

export const theme = writable<'light' | 'dark'>('light');
export const searchQuery = writable('');

export function initTheme() {
    const saved = localStorage.getItem('kalli-theme') as 'light' | 'dark' | null;
    const value = saved || 'light';
    theme.set(value);
    document.documentElement.dataset.theme = value;
}

export function toggleTheme() {
    const current = get(theme);
    const next = current === 'light' ? 'dark' : 'light';
    theme.set(next);
    localStorage.setItem('kalli-theme', next);
    document.documentElement.dataset.theme = next;
}

export interface FrameData {
    type: string;
    show: boolean;
    data: Record<string, unknown>;
    source?: string;
    display_name?: string;
    panel?: 'top' | 'bottom';
}

export type DisplayLayout = 'top' | 'split' | 'bottom';
export type ActivePage = 'assistants' | 'requirements' | 'tools';

export const activeFrame = writable<FrameData | null>(null);
export const topFrame = writable<FrameData | null>(null);
export const bottomFrame = writable<FrameData | null>(null);
export const activePage = writable<ActivePage>('assistants');
export const creatingItem = writable<boolean>(false);

export const displayLayout = derived(
    [topFrame, bottomFrame, creatingItem],
    ([$top, $bottom, $creating]) => {
        if ($top && ($bottom || $creating)) return 'split' as DisplayLayout;
        if ($top) return 'top' as DisplayLayout;
        return 'bottom' as DisplayLayout;
    },
);

export function clearFrames() {
    activeFrame.set(null);
    topFrame.set(null);
    bottomFrame.set(null);
    creatingItem.set(false);
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

export function showPage(page: ActivePage) {
    activePage.set(page);
    creatingItem.set(false);
}
