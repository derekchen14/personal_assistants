import { writable, derived, get } from 'svelte/store';

export const theme = writable<'light' | 'dark'>('light');

export function initTheme() {
    const saved = localStorage.getItem('dana-theme') as 'light' | 'dark' | null;
    const value = saved || 'light';
    theme.set(value);
    document.documentElement.dataset.theme = value;
}

export function toggleTheme() {
    const current = get(theme);
    const next = current === 'light' ? 'dark' : 'light';
    theme.set(next);
    localStorage.setItem('dana-theme', next);
    document.documentElement.dataset.theme = next;
}

export interface ArtifactData {
    type: string;
    show: boolean;
    data: Record<string, unknown>;
    source?: string;
    display_name?: string;
    panel?: 'top' | 'bottom';
}

export type DisplayLayout = 'top' | 'split' | 'bottom';
export type ActivePage = 'sheets' | 'queries' | 'metrics';

export const activeFrame = writable<ArtifactData | null>(null);
export const topFrame = writable<ArtifactData | null>(null);
export const bottomFrame = writable<ArtifactData | null>(null);
export const activePage = writable<ActivePage>('sheets');
export const searchQuery = writable('');
export const creatingItem = writable<boolean>(false);

const _expanded = writable(false);

export const displayLayout = derived(
    [topFrame, bottomFrame, _expanded, creatingItem],
    ([$top, $bottom, $exp, $creating]) => {
        if ($exp && $bottom) return 'bottom' as DisplayLayout;
        if ($top && ($bottom || $creating)) return 'split' as DisplayLayout;
        if ($top) return 'top' as DisplayLayout;
        return 'bottom' as DisplayLayout;
    },
);

export function showPage(page: ActivePage) {
    activePage.set(page);
    creatingItem.set(false);
}

export function clearFrames() {
    activeFrame.set(null);
    topFrame.set(null);
    bottomFrame.set(null);
    _expanded.set(false);
    creatingItem.set(false);
}

export function setFrame(artifact: ArtifactData) {
    console.log('[display] setFrame type=%s panel=%s show=%s', artifact.type, artifact.panel, artifact.show);
    activeFrame.set(artifact);
    const panel = artifact.panel || 'bottom';
    if (panel === 'top') {
        topFrame.set(artifact);
    } else {
        bottomFrame.set(artifact);
    }
}

export function expandPost() {
    _expanded.set(true);
}

export function collapsePost() {
    _expanded.set(false);
}
