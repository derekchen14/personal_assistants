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
export type ActivePage = 'posts' | 'drafts' | 'notes';

export const activeFrame = writable<FrameData | null>(null);
export const topFrame = writable<FrameData | null>(null);
export const bottomFrame = writable<FrameData | null>(null);
export const activePage = writable<ActivePage>('posts');

const _expanded = writable(false);
const _listExpanded = writable(false);

export const displayLayout = derived(
    [topFrame, bottomFrame, _expanded, _listExpanded],
    ([$top, $bottom, $exp, $listExp]) => {
        if ($listExp && $top) return 'top' as DisplayLayout;
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
    _listExpanded.set(false);
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
    _expanded.set(false);
    topFrame.update((current) => {
        if (current) return current;
        return { type: 'list', show: true, data: { title: 'Your Posts', items: [], source: 'welcome' }, source: 'welcome', panel: 'top' };
    });
}

export function expandPost() {
    _listExpanded.set(false);
    _expanded.set(true);
}

export function collapsePost() {
    _expanded.set(false);
}

export function expandList() {
    _expanded.set(false);
    _listExpanded.set(true);
}

export function collapseList() {
    _listExpanded.set(false);
}
