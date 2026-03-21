/**
 * Data store — tracks the currently active (selected) item.
 *
 * When the user clicks an item in ListBlock, the full item object is stored
 * here so any component can access it without prop-drilling.
 *
 * Why a separate store (not merged into display.ts):
 *   display.ts owns UI layout (frames, page, creating flag).
 *   data.ts owns the business data object.  They change at different rates
 *   and for different reasons, so keeping them separate avoids unnecessary
 *   re-renders and makes each store easier to reason about.
 *
 * Domain-specific: replace `Record<string, unknown>` with your actual entity
 * type once you know what fields an active item has.
 */

import { writable } from 'svelte/store';

/**
 * The currently selected item, or null if nothing is selected.
 * Set by the conversation store after a successful `select_entity*` call.
 */
export const activeItem = writable<Record<string, unknown> | null>(null);
