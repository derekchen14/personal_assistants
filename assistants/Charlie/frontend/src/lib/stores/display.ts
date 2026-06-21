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
    panel: 'top' | 'bottom';
    expand?: boolean;
}

// A2A v1.0 Part: exactly one of text / raw / url / data is set. Optional metadata extension.
export type Part =
    | { text: string;  metadata?: Record<string, unknown> }
    | { raw:  string;  metadata?: Record<string, unknown> }  // base64-encoded bytes
    | { url:  string;  metadata?: Record<string, unknown> }
    | { data: Record<string, unknown>; metadata?: Record<string, unknown> };

export interface ArtifactData {
    origin?: string;
    blocks?: Block[];
    parts?: Part[];
}

function firstBlock(artifact: ArtifactData | null): Block | undefined {
    return artifact?.blocks?.[0];
}

export type DisplayLayout = 'top' | 'split' | 'bottom';
export type ActivePage = 'posts' | 'drafts' | 'notes' | 'tags';

export const activePanel = writable<ArtifactData | null>(null);
export const topPanel = writable<ArtifactData | null>(null);
export const bottomPanel = writable<ArtifactData | null>(null);
export const drawer = writable<Block | null>(null);
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
    [topPanel, bottomPanel, _expanded, _listExpanded],
    ([$top, $bottom, $exp, $listExp]) => {
        if ($listExp && $top) return 'top' as DisplayLayout;
        if ($exp && $bottom) return 'bottom' as DisplayLayout;
        if ($top && $bottom) return 'split' as DisplayLayout;
        if ($top) return 'top' as DisplayLayout;
        return 'bottom' as DisplayLayout;
    },
);

export function clearPanels() {
    activePanel.set(null);
    topPanel.set(null);
    bottomPanel.set(null);
    dismissDrawer();
    _expanded.set(false);
    _listExpanded.set(false);
}

let _drawerTimer: ReturnType<typeof setTimeout> | null = null;

export function setDrawer(block: Block, dismissMs = 4000) {
    if (_drawerTimer) clearTimeout(_drawerTimer);
    drawer.set(block);
    _drawerTimer = setTimeout(() => {
        drawer.set(null);
        _drawerTimer = null;
    }, dismissMs);
}

export function dismissDrawer() {
    if (_drawerTimer) { clearTimeout(_drawerTimer); _drawerTimer = null; }
    drawer.set(null);
}

// Block types that render as transient overlays above their target panel rather than as persistent
// content inside it. Toast is the canonical case; extend this set if other transient types arrive.
const TRANSIENT_BLOCK_TYPES = new Set(['toast']);

export function setPanel(artifact: ArtifactData) {
    // Blockless artifact (e.g. inspect, clarification) carries chat-only content — metadata / thoughts but
    // nothing to render. Leave panels alone so the user's current view (card, list, grid) survives.
    const blocks = artifact.blocks ?? [];
    if (blocks.length === 0) return;
    const primary = blocks[0];
    if (primary.type === 'card' && (primary.data as Record<string, unknown>)?.status === 'note') return;
    activePanel.set(artifact);
    if (artifact.origin === 'find' && (primary.data as Record<string, unknown>)?.page) {
        showPage((primary.data as Record<string, unknown>).page as ActivePage);
    }

    let hasTopPersistent = false, hasBottomPersistent = false;
    for (const block of blocks) {
        // Decide the panel first — every block is anchored to a panel.
        const panel = block.panel ?? 'bottom';
        // Then decide persistent (lives in the panel) vs transient (drawer over the panel).
        const transient = TRANSIENT_BLOCK_TYPES.has(block.type);
        if (transient) {
            setDrawer(block);
        } else if (panel === 'top') {
            hasTopPersistent = true;
        } else {
            hasBottomPersistent = true;
        }
    }
    if (hasTopPersistent) {
        topPanel.set(artifact);
    }
    if (hasBottomPersistent) {
        _listExpanded.set(false);
        bottomPanel.set(artifact);
        if (primary.expand) {
            _expanded.set(true);
        }
    }
}

export function showChosenOutline(
    outline: Array<{ name: string; description?: string }>,
    priorData: Record<string, unknown> = {},
) {
    const content = outline
        .map(sec => `## ${sec.name}\n\n${sec.description ?? ''}`)
        .join('\n\n');
    const artifact: ArtifactData = {
        origin: 'outline',
        blocks: [{
            type: 'card',
            panel: 'bottom',
            data: { ...priorData, content, pending: true },
        }],
    };
    activePanel.set(artifact);
    bottomPanel.set(artifact);
}

let _onRefresh: ((frameType: string) => void) | null = null;

export function setRefreshCallback(cb: (frameType: string) => void) {
    _onRefresh = cb;
}

export function showPage(page: ActivePage) {
    activePage.set(page);
    _expanded.set(false);
    const frameType = page === 'notes' ? 'grid' : 'list';
    topPanel.update((current) => {
        const data = firstBlock(current ?? null)?.data ?? { items: [] };
        const block: Block = { type: frameType, data, panel: 'top' };
        if (current) return { ...current, blocks: [block] };
        return { origin: '', blocks: [block] };
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
