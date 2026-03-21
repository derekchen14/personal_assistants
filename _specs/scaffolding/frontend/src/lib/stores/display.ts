/**
 * Display store — layout, frames, navigation, and creating state.
 *
 * Four stores in this file:
 *   topFrame      — the frame currently shown in the top panel (ListBlock)
 *   bottomFrame   — the frame currently shown in the bottom panel (CardBlock)
 *   activePage    — which entity tab is active in the nav (drives ListBlock filtering)
 *   creatingItem  — boolean: is the ghost creation panel showing?
 *
 * One derived store:
 *   displayLayout — computed from topFrame, bottomFrame, _expanded, creatingItem
 *
 * Key pattern: showPage() vs setting activePage directly.
 *   ALWAYS use showPage(page) instead of activePage.set(page).
 *   showPage() atomically sets the page AND clears creatingItem, preventing
 *   a stale ghost panel from persisting when the user navigates away.
 *
 * creatingItem lives here (not in conversation.ts) because it is a pure UI
 * concern — it controls which panel is shown, not any backend state.
 *
 * Domain-specific: extend ActivePage with your entity tab names.
 */

import { writable, derived, get } from 'svelte/store';

// ── Types ──────────────────────────────────────────────────────────────────

export interface FrameData {
    type: string;               // 'list' | 'grid' | 'card' | 'chart' | 'text'
    show: boolean;
    data: Record<string, unknown>;
    source?: string;            // 'welcome' | 'select' | 'create' | 'update'
    display_name?: string;
    panel?: 'top' | 'bottom';  // which panel to render in
}

// 'top'    — only the top panel is visible (list/grid fills full display area)
// 'split'  — both top and bottom panels are visible
// 'bottom' — only the bottom panel is visible (expanded card)
export type DisplayLayout = 'top' | 'split' | 'bottom';

// Domain-specific: add your entity tab names here.
// Example (Dana): 'sheets' | 'queries' | 'metrics'
// Example (Kalli): 'requirements' | 'tools' | 'skills'
export type ActivePage = 'entity1s' | 'entity2s' | 'entity3s';


// ── Writable stores ────────────────────────────────────────────────────────

export const topFrame = writable<FrameData | null>(null);
export const bottomFrame = writable<FrameData | null>(null);

// The active entity tab — which section ListBlock should show.
// Always set via showPage(), never directly.
export const activePage = writable<ActivePage>('entity1s');

// Search input value, shared between the header search box and ListBlock.
export const searchQuery = writable('');

// True when the ghost creation panel should show in the bottom pane.
// Cleared by showPage() and clearFrames().
export const creatingItem = writable<boolean>(false);

// Private — only used by the displayLayout derivation.
// Consumers call expandPost() / collapsePost() rather than setting this directly.
const _expanded = writable(false);


// ── Derived: layout ────────────────────────────────────────────────────────

/**
 * Compute the current panel layout from all relevant state.
 *
 * Why derive from four args (not just top/bottom):
 *   - _expanded=true means the bottom card is full-screen → 'bottom'
 *   - creatingItem=true means we need the bottom pane even when bottomFrame
 *     is null (the ghost form lives there) → 'split'
 *
 * Layout rules (in priority order):
 *   1. Expanded + bottomFrame → 'bottom' (full-screen card)
 *   2. topFrame + (bottomFrame OR creatingItem) → 'split'
 *   3. topFrame only → 'top'
 *   4. Fallback → 'bottom' (default empty state)
 */
export const displayLayout = derived(
    [topFrame, bottomFrame, _expanded, creatingItem],
    ([$top, $bottom, $exp, $creating]) => {
        if ($exp && $bottom) return 'bottom' as DisplayLayout;
        if ($top && ($bottom || $creating)) return 'split' as DisplayLayout;
        if ($top) return 'top' as DisplayLayout;
        return 'bottom' as DisplayLayout;
    },
);


// ── Navigation ─────────────────────────────────────────────────────────────

/**
 * Switch the active entity tab.
 *
 * Use this instead of activePage.set() directly.
 * The atomic clear of creatingItem prevents a ghost creation form from
 * persisting when the user navigates to a different tab.
 */
export function showPage(page: ActivePage) {
    activePage.set(page);
    creatingItem.set(false);
}


// ── Frame routing ──────────────────────────────────────────────────────────

/**
 * Route an incoming frame to the correct panel store.
 *
 * Called from +page.svelte's $effect whenever a new agent message arrives.
 * The frame's `panel` field (set by the backend) determines which store is
 * updated.  Defaults to 'bottom' if panel is missing.
 */
export function setFrame(frame: FrameData) {
    console.log('[display] setFrame type=%s panel=%s', frame.type, frame.panel);
    const panel = frame.panel || 'bottom';
    if (panel === 'top') {
        topFrame.set(frame);
    } else {
        bottomFrame.set(frame);
    }
}


// ── Reset ──────────────────────────────────────────────────────────────────

/**
 * Clear all display state.
 *
 * Called on logout, session reset, and WebSocket disconnect.
 * Resets everything including creatingItem — no stale ghost panels after logout.
 */
export function clearFrames() {
    topFrame.set(null);
    bottomFrame.set(null);
    _expanded.set(false);
    creatingItem.set(false);
}


// ── Expand / collapse ──────────────────────────────────────────────────────

/** Expand the bottom card to full-screen (hides the top panel). */
export function expandPost() {
    _expanded.set(true);
}

/** Collapse back to split view. */
export function collapsePost() {
    _expanded.set(false);
}
