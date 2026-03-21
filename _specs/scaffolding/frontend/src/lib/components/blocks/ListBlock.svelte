<script lang="ts">
    /**
     * ListBlock — sectioned entity list with CRUD controls.
     *
     * Two rendering modes:
     *   Sectioned (source === 'welcome' OR items have 'entity' tags):
     *     Shows the entity tab that matches $activePage.  Includes delete
     *     buttons and a "+ New" create button.  This is the standard mode
     *     for the top panel of the main app.
     *
     *   Flat (all other sources):
     *     A plain numbered or bulleted list.  Used for agent-generated lists
     *     (e.g., brainstorm results, search results) that don't need CRUD.
     *
     * ENTITY_MAP:    activePage key → entity tag string (used for filtering)
     * HEADING_MAP:   activePage key → section heading text
     * EMPTY_MAP:     activePage key → empty-state message
     * CREATE_PAGES:  set of pages that show a "+ New" button
     * CREATE_LABEL:  activePage key → button label
     *
     * itemId():   extracts the unique ID for an item (used for delete, select)
     * itemLabel(): extracts the display label (entity-aware — queries truncate)
     *
     * Confirm delete dialog:
     *   confirmDeleteItem holds the item pending deletion.  A modal overlay
     *   appears and the user must confirm.  Don't use browser confirm() —
     *   it blocks the UI thread and looks inconsistent across platforms.
     *
     * Create button:
     *   Sets creatingItem to true.  The ghost creation form in +page.svelte's
     *   bottom pane activates.  ListBlock doesn't own the form — it only
     *   triggers the display state.
     *
     * Domain-specific: update ENTITY_MAP, HEADING_MAP, EMPTY_MAP, CREATE_PAGES,
     * CREATE_LABEL, itemId(), and itemLabel() to match your entity names.
     */

    import { conversation } from '$lib/stores/conversation';
    import { activePage, searchQuery, creatingItem } from '$lib/stores/display';

    let { data }: { data: Record<string, unknown> } = $props();

    let items = $derived((data.items as unknown[]) || []);
    let title = $derived((data.title as string) || '');
    let content = $derived((data.content as string) || '');
    let ordered = $derived((data.ordered as boolean) || false);
    let source = $derived((data.source as string) || '');

    // Sectioned mode when source is 'welcome' or any item has an 'entity' tag.
    let isSectioned = $derived(source === 'welcome' || items.some(
        (it) => typeof it === 'object' && it !== null && 'entity' in (it as Record<string, unknown>)
    ));

    // ── Entity maps ──────────────────────────────────────────────────────────
    // Domain-specific: rename keys and values to match your entities.

    // Maps activePage key → entity tag value used in item objects
    const ENTITY_MAP: Record<string, string> = {
        entity1s: 'entity1',
        entity2s: 'entity2',
        entity3s: 'entity3',
    };

    // Section heading shown above the list for each page
    const HEADING_MAP: Record<string, string> = {
        entity1s: 'Your Entity1s',   // Domain-specific: e.g., 'Your Sheets'
        entity2s: 'Your Entity2s',   // Domain-specific: e.g., 'Your Queries'
        entity3s: 'Your Entity3s',   // Domain-specific: e.g., 'Your Metrics'
    };

    // Empty-state message when no items exist for this page
    const EMPTY_MAP: Record<string, string> = {
        entity1s: 'No entity1s yet',
        entity2s: 'No entity2s yet',
        entity3s: 'No entity3s yet',
    };

    // Only pages in CREATE_PAGES show a "+ New" button.
    // Read-only entity pages (entity1s) are typically excluded.
    const CREATE_PAGES = new Set(['entity2s', 'entity3s']);

    // Label on the "+ New" button for each page
    const CREATE_LABEL: Record<string, string> = {
        entity2s: '+ New Entity2',   // Domain-specific
        entity3s: '+ New Entity3',   // Domain-specific
    };

    // ── Item helpers ─────────────────────────────────────────────────────────

    // Returns the unique ID for an item, used for select/delete calls.
    // Branch by entity type because each entity has a different ID field name.
    function itemId(item: unknown): string | null {
        if (typeof item !== 'object' || item === null) return null;
        const o = item as Record<string, unknown>;
        if (o.entity === 'entity1') return (o.entity1_id as string) || null;
        if (o.entity === 'entity2') return (o.entity2_id as string) || null;
        if (o.entity === 'entity3') return (o.entity3_id as string) || null;
        return null;
    }

    // Returns the display label for an item.
    // entity2 (plain text): truncate long text to 60 chars for list readability.
    // Others: use name, title, or display_name field.
    function itemLabel(item: unknown): string {
        if (typeof item === 'string') return item;
        if (typeof item === 'object' && item !== null) {
            const o = item as Record<string, unknown>;
            if (o.entity === 'entity2') {
                // Truncate long text (e.g., SQL queries) for list display
                const text = (o.text as string) || '';
                return text.length > 60 ? text.slice(0, 60) + '…' : text;
            }
            return (o.name || o.title || o.display_name || '') as string;
        }
        return String(item);
    }

    function matchesSearch(item: unknown, query: string): boolean {
        if (!query) return true;
        return itemLabel(item).toLowerCase().includes(query.toLowerCase());
    }

    function getField(item: unknown, field: string): string {
        if (typeof item === 'object' && item !== null) {
            return ((item as Record<string, unknown>)[field] as string) || '';
        }
        return '';
    }

    // Items for the currently active page, filtered by search query
    let pageItems = $derived(
        isSectioned
            ? items
                .filter((it) => getField(it, 'entity') === ENTITY_MAP[$activePage])
                .filter((it) => matchesSearch(it, $searchQuery))
            : []
    );

    // ── Delete confirmation ──────────────────────────────────────────────────
    // Holds the item awaiting delete confirmation; null when no dialog is open.
    // Don't use browser confirm() — it blocks the thread and looks inconsistent.
    let confirmDeleteItem: unknown | null = $state(null);

    // ── Event handlers ───────────────────────────────────────────────────────

    function handleClick(item: unknown) {
        const o = item as Record<string, unknown>;
        if (o.entity === 'entity1') {
            conversation.selectEntity1(o.entity1_id as string);
        } else if (o.entity === 'entity2') {
            conversation.selectEntity2(o.entity2_id as string);
        } else if (o.entity === 'entity3') {
            conversation.selectEntity3(o.entity3_id as string);
        }
    }

    function handleDelete(item: unknown) {
        const o = item as Record<string, unknown>;
        if (o.entity === 'entity2') {
            conversation.deleteEntity2(o.entity2_id as string);
        } else if (o.entity === 'entity3') {
            conversation.deleteEntity3(o.entity3_id as string);
        }
        confirmDeleteItem = null;
    }
</script>

{#if isSectioned}
    <div class="px-2">
        <h2 class="text-center text-lg font-semibold underline text-[var(--secondary)] mb-4">
            {HEADING_MAP[$activePage]}
        </h2>

        {#if pageItems.length > 0}
            <div class="space-y-1 text-base px-2">
                {#each pageItems as item}
                    {@const id = itemId(item)}
                    {@const isReadOnly = (item as Record<string, unknown>).entity === 'entity1'}
                    <div
                        class="group flex items-center gap-2 py-2 px-2 rounded cursor-pointer hover:bg-[var(--hover)]"
                        onclick={() => handleClick(item)}
                        role="button"
                        tabindex="0"
                        onkeydown={(e) => { if (e.key === 'Enter') handleClick(item); }}
                    >
                        {#if ordered}
                            <span class="text-[var(--muted)] w-5 shrink-0 text-right">
                                {pageItems.indexOf(item) + 1}.
                            </span>
                        {/if}
                        <span class="flex-1 font-semibold group-hover:underline">{itemLabel(item)}</span>

                        <!-- Delete button: hidden for read-only entities -->
                        {#if !isReadOnly && id}
                            <button
                                class="opacity-0 group-hover:opacity-100 transition-opacity text-[var(--muted)] hover:text-red-500 cursor-pointer shrink-0 text-xs"
                                title="Delete"
                                onclick={(e) => { e.stopPropagation(); confirmDeleteItem = item; }}
                            >
                                ✕
                            </button>
                        {/if}
                    </div>
                {/each}
            </div>
        {:else}
            <p class="text-sm text-[var(--muted)] text-center">{EMPTY_MAP[$activePage]}</p>
        {/if}

        <!-- Create button: only shown for pages in CREATE_PAGES -->
        {#if CREATE_PAGES.has($activePage)}
            <div class="flex justify-center mt-4">
                <button
                    class="inline-flex items-center gap-1 py-1.5 px-4 text-sm font-medium text-[var(--accent)] border border-[var(--accent)] rounded-md bg-transparent cursor-pointer transition-colors hover:bg-[var(--accent)] hover:text-white"
                    onclick={() => creatingItem.set(true)}
                >
                    {CREATE_LABEL[$activePage]}
                </button>
            </div>
        {/if}
    </div>

{:else if items.length > 0}
    <!-- Flat list (non-sectioned): agent-generated lists, search results, etc. -->
    {#if title}
        <h3 class="text-base font-medium mb-3 text-[var(--secondary)]">{title}</h3>
    {/if}
    <div class="space-y-1 text-base px-2">
        {#each items as item, i}
            <div class="flex gap-2 py-2 px-2 rounded">
                {#if ordered}
                    <span class="text-[var(--muted)] w-5 shrink-0 text-right">{i + 1}.</span>
                {/if}
                <span>{itemLabel(item)}</span>
            </div>
        {/each}
    </div>

{:else if content}
    <div class="text-base leading-relaxed">{content}</div>
{/if}

<!-- Confirm delete dialog ─────────────────────────────────────────────────────
  A modal overlay with Cancel and Delete buttons.
  Clicking the backdrop cancels.  The dialog itself stops propagation.
-->
{#if confirmDeleteItem}
    <div
        class="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
        onclick={() => confirmDeleteItem = null}
        role="presentation"
    >
        <div
            class="bg-[var(--surface)] border border-[var(--border)] rounded-lg py-5 px-6 max-w-xs w-[90%] shadow-lg"
            onclick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
        >
            <p class="text-sm font-medium mb-1">Delete "{itemLabel(confirmDeleteItem)}"?</p>
            <p class="text-xs text-[var(--muted)] mb-4">This action cannot be undone.</p>
            <div class="flex justify-end gap-2">
                <button
                    class="px-3 py-1.5 text-xs rounded border border-[var(--border)] text-[var(--muted)] hover:text-[var(--text)] cursor-pointer transition-colors"
                    onclick={() => confirmDeleteItem = null}
                >
                    Cancel
                </button>
                <button
                    class="px-3 py-1.5 text-xs rounded bg-red-500 hover:bg-red-600 text-white font-medium cursor-pointer transition-colors"
                    onclick={() => handleDelete(confirmDeleteItem)}
                >
                    Delete
                </button>
            </div>
        </div>
    </div>
{/if}
