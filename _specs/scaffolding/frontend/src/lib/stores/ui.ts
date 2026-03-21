/**
 * UI store — lightweight loading state.
 *
 * Kept as a separate store (not merged into conversation) so that components
 * can import only what they need.  The loading spinner and disabled-input
 * state derive from `isLoading`; nothing else needs to live here.
 *
 * Why a separate store:
 *   Merging loading state into conversation.ts would create unnecessary
 *   re-renders in components that only care about loading (e.g., the send
 *   button) but import conversation to get messages.
 */

import { writable } from 'svelte/store';

/**
 * True while the agent is processing a turn.
 * Set to true when a message is sent, false when the agent response arrives.
 * The conversation store manages this flag — UI components just read it.
 */
export const isLoading = writable<boolean>(false);
