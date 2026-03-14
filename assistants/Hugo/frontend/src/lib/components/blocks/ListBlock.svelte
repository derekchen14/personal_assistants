<script lang="ts">
    import { conversation } from '$lib/stores/conversation';
    import { activePage, displayLayout, expandPost, expandList, collapseList, bottomFrame } from '$lib/stores/display';
    import IconArrowsPointingOut from '$lib/assets/IconArrowsPointingOut.svelte';
    import IconArrowsPointingIn from '$lib/assets/IconArrowsPointingIn.svelte';
    import IconTrash from '$lib/assets/IconTrash.svelte';

    let confirmDeleteItem: unknown | null = $state(null);

    let { data }: { data: Record<string, unknown> } = $props();

    let items = $derived((data.items as unknown[]) || []);
    let title = $derived((data.title as string) || '');
    let content = $derived((data.content as string) || '');
    let ordered = $derived((data.ordered as boolean) || false);
    let source = $derived((data.source as string) || '');

    let expandedId: string | null = $state(null);

    // Section items by status when source is 'welcome' or items have status
    let isSectioned = $derived(source === 'welcome' || items.some(
        (it) => typeof it === 'object' && it !== null && 'status' in (it as Record<string, unknown>)
    ));

    const STATUS_MAP: Record<string, string> = {
        posts: 'published',
        drafts: 'draft',
        notes: 'note',
    };

    const HEADING_MAP: Record<string, string> = {
        posts: 'Your Posts',
        drafts: 'Your Drafts',
        notes: 'Your Notes',
    };

    const EMPTY_MAP: Record<string, string> = {
        posts: 'No published posts yet',
        drafts: 'No drafts yet',
        notes: 'No notes yet',
    };

    let pageItems = $derived(
        isSectioned
            ? items.filter((it) => getField(it, 'status') === STATUS_MAP[$activePage])
            : []
    );

    function itemLabel(item: unknown): string {
        if (typeof item === 'string') return item;
        if (typeof item === 'object' && item !== null) {
            const o = item as Record<string, unknown>;
            return (o.title || o.name || o.display_name || '') as string;
        }
        return String(item);
    }

    function itemId(item: unknown): string | null {
        if (typeof item === 'object' && item !== null) {
            return ((item as Record<string, unknown>).post_id as string) || null;
        }
        return null;
    }

    function handleClick(item: unknown) {
        const id = itemId(item);
        if (!id) return;

        if (expandedId === id) {
            expandedId = null;
        } else {
            expandedId = id;
            conversation.selectPost(id);
        }
    }

    function handleViewPost(id: string) {
        conversation.viewPost(id);
        expandPost();
    }

    function getPreview(item: unknown): string {
        if (typeof item === 'object' && item !== null) {
            return ((item as Record<string, unknown>).preview as string) || '';
        }
        return '';
    }

    function getMetadata(item: unknown): Record<string, unknown> {
        if (typeof item === 'object' && item !== null) {
            return ((item as Record<string, unknown>).metadata as Record<string, unknown>) || {};
        }
        return {};
    }

    function getTags(item: unknown): string[] {
        const meta = getMetadata(item);
        const tags = meta.tags;
        if (Array.isArray(tags)) return tags as string[];
        return [];
    }

    function getDate(item: unknown): string {
        if (typeof item !== 'object' || item === null) return '';
        const o = item as Record<string, unknown>;
        const date = (o.updated_at || o.created_at || '') as string;
        if (!date) return '';
        try {
            return new Date(date).toLocaleDateString('en-US', {
                year: 'numeric', month: 'short', day: 'numeric',
            });
        } catch {
            return date;
        }
    }

    function getField(item: unknown, field: string): string {
        if (typeof item === 'object' && item !== null) {
            return ((item as Record<string, unknown>)[field] as string) || '';
        }
        return '';
    }

    const CREATE_PAGES = new Set(['drafts', 'notes']);

    const CREATE_LABEL: Record<string, string> = {
        drafts: '+ New Draft',
        notes: '+ New Note',
    };

    const CREATE_TYPE: Record<string, 'draft' | 'note'> = {
        drafts: 'draft',
        notes: 'note',
    };

    function handleCreate() {
        const type = CREATE_TYPE[$activePage];
        if (type) {
            conversation.createPost(type);
        }
    }

    const VIEW_LABEL: Record<string, string> = {
        published: 'View Full Post',
        draft: 'View Full Draft',
        note: 'View Full Note',
    };

    function getViewLabel(item: unknown): string {
        const status = getField(item, 'status');
        return VIEW_LABEL[status] || 'View Full Post';
    }
</script>

{#snippet itemRow(item: unknown, i: number)}
    {@const id = itemId(item)}
    {@const clickable = !!id}
    {@const expanded = id !== null && expandedId === id}
    <div class="rounded {expanded ? 'bg-[var(--surface)] border border-[var(--border)] mb-2' : ''}">
        <div
            class="flex gap-2 py-2 px-2 rounded {clickable ? 'cursor-pointer' : ''}"
            onclick={() => handleClick(item)}
            role={clickable ? 'button' : undefined}
            tabindex={clickable ? 0 : undefined}
            onkeydown={(e) => { if (clickable && e.key === 'Enter') handleClick(item); }}
        >
            {#if ordered}
                <span class="text-[var(--muted)] w-5 shrink-0 text-right">{i + 1}.</span>
            {/if}
            <span class="font-semibold {clickable ? 'hover:underline transition-colors' : ''} {expanded ? 'text-[var(--accent)]' : ''}">
                {itemLabel(item)}
            </span>
        </div>

        {#if expanded}
            <div class="px-4 pb-3 pt-1 space-y-2 border-t border-[var(--border)] ml-4 mr-2">
                {#if getDate(item)}
                    <div class="text-xs text-[var(--muted)]">
                        {getDate(item)}
                        {#if getField(item, 'category')}
                            <span class="mx-1">&middot;</span>
                            <span>{getField(item, 'category')}</span>
                        {/if}
                    </div>
                {/if}

                {#if getTags(item).length > 0}
                    <div class="flex flex-wrap gap-1.5">
                        {#each getTags(item) as tag}
                            <span class="tag-badge">{tag}</span>
                        {/each}
                    </div>
                {/if}

                {#if getPreview(item)}
                    <p class="text-sm leading-relaxed text-[var(--muted)] line-clamp-4">
                        {getPreview(item)}
                    </p>
                {/if}

                <div class="flex items-center justify-between mt-1">
                    <button
                        class="text-xs text-[var(--accent)] hover:text-[var(--accent-dark)] font-medium cursor-pointer"
                        onclick={(e) => { e.stopPropagation(); handleViewPost(id!); }}
                    >
                        {getViewLabel(item)} &rarr;
                    </button>
                    {#if getField(item, 'status') === 'draft' || getField(item, 'status') === 'note'}
                        <button
                            class="text-[var(--muted)] hover:text-red-500 cursor-pointer transition-colors"
                            title="Delete"
                            onclick={(e) => { e.stopPropagation(); confirmDeleteItem = item; }}
                        >
                            <IconTrash size={14} />
                        </button>
                    {/if}
                </div>
            </div>
        {/if}
    </div>
{/snippet}

{#if isSectioned}
    <!-- Single-page view based on active header tab -->
    <div class="px-2 relative">
        {#if $activePage === 'notes'}
            <button
                onclick={() => $displayLayout === 'top' ? collapseList() : expandList()}
                class="absolute top-0 right-2 text-[var(--muted)] hover:text-[var(--accent)] cursor-pointer transition-colors"
                title={$displayLayout === 'top' ? 'Collapse' : 'Expand'}
            >
                {#if $displayLayout === 'top'}
                    <IconArrowsPointingIn size={18} />
                {:else}
                    <IconArrowsPointingOut size={18} />
                {/if}
            </button>
        {/if}
        <h2 class="text-center text-lg font-semibold underline text-[var(--secondary)] mb-4">{HEADING_MAP[$activePage]}</h2>
        {#if pageItems.length > 0}
            <div class="space-y-1 text-base px-2">
                {#each pageItems as item, i}
                    {@render itemRow(item, i)}
                {/each}
            </div>
        {:else}
            <p class="text-sm text-[var(--muted)] text-center">{EMPTY_MAP[$activePage]}</p>
        {/if}
        {#if CREATE_PAGES.has($activePage)}
            <div class="flex justify-center mt-4">
                <button class="create-btn" onclick={handleCreate}>
                    {CREATE_LABEL[$activePage]}
                </button>
            </div>
        {/if}
    </div>
{:else if items.length > 0}
    <!-- Flat list (non-sectioned) -->
    {#if title}
        <h3 class="text-base font-medium mb-3 text-[var(--secondary)]">{title}</h3>
    {/if}
    <div class="space-y-1 text-base px-2">
        {#each items as item, i}
            {@render itemRow(item, i)}
        {/each}
    </div>
{:else if content}
    <div class="text-base leading-relaxed">{content}</div>
{/if}

{#if confirmDeleteItem}
    <div class="modal-overlay" onclick={() => confirmDeleteItem = null} role="presentation">
        <div class="modal-box" onclick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
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
                    onclick={() => {
                        const id = itemId(confirmDeleteItem);
                        if (id) {
                            conversation.deletePost(id);
                            if (expandedId === id) expandedId = null;
                            bottomFrame.set(null);
                        }
                        confirmDeleteItem = null;
                    }}
                >
                    Delete
                </button>
            </div>
        </div>
    </div>
{/if}

<style>
    .modal-overlay {
        position: fixed;
        inset: 0;
        background: rgba(0, 0, 0, 0.4);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 50;
    }
    .modal-box {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 1.25rem 1.5rem;
        max-width: 320px;
        width: 90%;
        box-shadow: 0 4px 24px rgba(0, 0, 0, 0.15);
    }
    .tag-badge {
        display: inline-block;
        font-size: 0.65rem;
        line-height: 1;
        padding: 2px 8px 2px 12px;
        border: 1px solid var(--border);
        border-radius: 0 4px 4px 0;
        color: var(--muted);
        background: var(--surface);
        position: relative;
    }
    .tag-badge::before {
        content: '';
        position: absolute;
        left: 0;
        top: 50%;
        transform: translateY(-50%);
        width: 0;
        height: 0;
        border-top: 9px solid transparent;
        border-bottom: 9px solid transparent;
        border-left: 6px solid var(--surface, #ffffff);
    }
    .create-btn {
        display: inline-flex;
        align-items: center;
        gap: 0.25rem;
        padding: 0.375rem 1rem;
        font-size: 0.8125rem;
        font-weight: 500;
        color: var(--accent);
        border: 1px solid var(--accent);
        border-radius: 6px;
        background: transparent;
        cursor: pointer;
        transition: background 0.15s, color 0.15s;
    }
    .create-btn:hover {
        background: var(--accent);
        color: var(--bg, #fff);
    }
</style>
