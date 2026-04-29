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

export interface Block {
    type: string;
    data: Record<string, unknown>;
    location: 'top' | 'bottom';
    expand?: boolean;
}

export interface FrameData {
    origin?: string;
    blocks?: Block[];
    metadata?: Record<string, unknown>;
    panel?: 'top' | 'bottom' | 'split';
    thoughts?: string;
}

function firstBlock(frame: FrameData | null): Block | undefined {
    return frame?.blocks?.[0];
}

export type DisplayLayout = 'top' | 'split' | 'bottom';
export type ActivePage = 'posts' | 'drafts' | 'notes' | 'tags';

export const activeFrame = writable<FrameData | null>(null);
export const topFrame = writable<FrameData | null>(null);
export const bottomFrame = writable<FrameData | null>(null);
export const lastCardFrame = writable<FrameData | null>(null);
export const activePage = writable<ActivePage>('posts');
export const activeTag = writable<string>('');
export const searchQuery = writable('');
export const activeHighlight = writable<string>('');
export const activeSection = writable<string>('');
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
    lastCardFrame.set(null);
    _expanded.set(false);
    _listExpanded.set(false);
}

export function setFrame(frame: FrameData) {
    // Blockless frame (e.g. inspect, clarification) carries chat-only content — metadata / thoughts but nothing
    // to render. Leave the display containers alone so the user's current view (card, list, grid) survives.
    const primary = firstBlock(frame);
    if (!primary) return;
    if (primary.type === 'card' && (primary.data as Record<string, unknown>)?.status === 'note') return;
    activeFrame.set(frame);
    if (frame.origin === 'find' && (primary.data as Record<string, unknown>)?.page) {
        showPage((primary.data as Record<string, unknown>).page as ActivePage);
    }
    const panel = frame.panel || 'bottom';
    if (primary.type === 'card' && panel === 'bottom') {
        lastCardFrame.set(frame);
    }
    if (panel === 'top') {
        topFrame.set(frame);
    } else if (panel === 'split') {
        topFrame.set(frame);
        bottomFrame.set(frame);
    } else {
        _listExpanded.set(false);
        bottomFrame.set(frame);
        if (primary.expand) {
            _expanded.set(true);
        }
    }
}

export function restorePendingCard() {
    const saved = get(lastCardFrame);
    if (!saved?.blocks?.length) return;
    const blocks = saved.blocks.map(b =>
        b.type === 'card' ? { ...b, data: { ...b.data, pending: true } } : b,
    );
    const pending: FrameData = { ...saved, blocks };
    activeFrame.set(pending);
    bottomFrame.set(pending);
}

export function showChosenOutline(outline: Array<{ name: string; description?: string }>) {
    const content = outline
        .map(sec => `## ${sec.name}\n\n${sec.description ?? ''}`)
        .join('\n\n');
    const saved = get(lastCardFrame);
    const priorCard = saved?.blocks?.find(b => b.type === 'card');
    const priorData = (priorCard?.data ?? {}) as Record<string, unknown>;
    const frame: FrameData = {
        origin: 'outline',
        panel: 'bottom',
        blocks: [{
            type: 'card',
            location: 'bottom',
            data: { ...priorData, content, pending: true },
        }],
    };
    activeFrame.set(frame);
    bottomFrame.set(frame);
    lastCardFrame.set(frame);
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
        const data = firstBlock(current ?? null)?.data ?? { items: [] };
        const block: Block = { type: frameType, data, location: 'top' };
        if (current) return { ...current, blocks: [block] };
        return { origin: 'welcome', panel: 'top', blocks: [block] };
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
