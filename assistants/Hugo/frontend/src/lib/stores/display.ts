import { writable, derived, get } from 'svelte/store';

export const theme = writable<'light' | 'dark'>('light');

export function initTheme() {
    const saved = localStorage.getItem('hugo-theme') as 'light' | 'dark' | null;
    const value = saved || 'light';
    theme.set(value);
    document.documentElement.dataset.theme = value;
}

export function toggleTheme() {
    const current = get(theme);
    const next = current === 'light' ? 'dark' : 'light';
    theme.set(next);
    localStorage.setItem('hugo-theme', next);
    document.documentElement.dataset.theme = next;
}

export interface FrameData {
    block_type: string;
    data: Record<string, unknown>;
    origin?: string;
    display_name?: string;
    panel?: 'top' | 'bottom';
}

export type DisplayLayout = 'top' | 'split' | 'bottom';
export type ActivePage = 'posts' | 'drafts' | 'notes' | 'tags';

export const activeFrame = writable<FrameData | null>(null);
export const topFrame = writable<FrameData | null>(null);
export const bottomFrame = writable<FrameData | null>(null);
export const activePage = writable<ActivePage>('posts');
export const activeTag = writable<string>('');
export const searchQuery = writable('');
export const activeHighlight = writable<string>('');
export const creatingPost = writable(false);
export const activePost = writable<string>('');

const _prevPage = writable<ActivePage>('posts');

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
    if (frame.block_type === 'card' && (frame.data as Record<string, unknown>)?.status === 'note') return;
    activeFrame.set(frame);
    const data = frame.data as Record<string, unknown>;
    if (frame.origin === 'find' && data?.page) {
        showPage(data.page as ActivePage);
    }
    const panel = frame.panel || 'bottom';
    if (panel === 'top') {
        topFrame.set(frame);
    } else {
        _listExpanded.set(false);
        bottomFrame.set(frame);
        if (frame.origin === 'create') {
            _expanded.set(true);
        }
    }
}

let _onRefresh: ((frameType: string) => void) | null = null;

export function setRefreshCallback(cb: (frameType: string) => void) {
    _onRefresh = cb;
}

export function showPage(page: ActivePage) {
    activePage.set(page);
    _expanded.set(false);
    const frameType = page === 'notes' ? 'grid' : 'list';
    topFrame.update((current) => {
        if (current) return { ...current, block_type: frameType };
        return { block_type: frameType, data: { items: [] }, origin: 'welcome', panel: 'top' };
    });
    _onRefresh?.(frameType);
}

export function showTagPage(tag: string) {
    _prevPage.set(get(activePage));
    activeTag.set(tag);
    activePage.set('tags');
    _expanded.set(false);
}

export function goBack() {
    activePage.set(get(_prevPage));
    activeTag.set('');
}

export function expandPost() {
    _listExpanded.set(false);
    _expanded.set(true);
}

export function collapsePost() {
    _expanded.set(false);
    const page = get(activePage);
    const frameType = page === 'notes' ? 'grid' : 'list';
    _onRefresh?.(frameType);
}

export function expandList() {
    _expanded.set(false);
    _listExpanded.set(true);
}

export function collapseList() {
    _listExpanded.set(false);
}
