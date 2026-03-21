<script lang="ts">
    import { conversation } from '$lib/stores/conversation';
    import { activePage, searchQuery, expandPost, expandList, bottomFrame, activeTag, showTagPage, goBack, creatingPost } from '$lib/stores/display';
    import IconTrash from '$lib/assets/IconTrash.svelte';
    import IconGripVertical from '$lib/assets/IconGripVertical.svelte';
    import IconArrowUturnLeft from '$lib/assets/IconArrowUturnLeft.svelte';
    import IconFunnel from '$lib/assets/IconFunnel.svelte';

    let confirmDeleteItem: unknown | null = $state(null);

    let { data, origin = '' }: { data: Record<string, unknown>; origin?: string } = $props();

    let items = $derived((data.items as unknown[]) || []);
    let title = $derived((data.title as string) || '');
    let content = $derived((data.content as string) || '');
    let ordered = $derived((data.ordered as boolean) || false);
    let autoExpanded = $derived(
        new Set<string>((data.expanded_ids as string[]) || [])
    );

    let expandedIds = $state(new Set<string>());
    $effect(() => { expandedIds = new Set(autoExpanded); });

    // ── Drag-and-drop ──────────────────────────────────────────────────────────
    let draggedId: string | null = $state(null);
    let dragOverId: string | null = $state(null);

    const RANKING_KEY = 'hugo-draft-ranking';

    function loadRanking(): Record<string, number> {
        if (typeof localStorage === 'undefined') return {};
        try { return JSON.parse(localStorage.getItem(RANKING_KEY) || '{}'); } catch { return {}; }
    }

    function saveRankingToStorage(r: Record<string, number>) {
        if (typeof localStorage !== 'undefined') localStorage.setItem(RANKING_KEY, JSON.stringify(r));
    }

    let ranking = $state<Record<string, number>>(loadRanking());

    function getItemRank(item: unknown): number {
        const id = itemId(item);
        return id ? (ranking[id] ?? 9999) : 9999;
    }

    function handleDrop(targetId: string | null) {
        if (!draggedId || !targetId || draggedId === targetId) return;
        const fromIdx = pageItems.findIndex(it => itemId(it) === draggedId);
        const toIdx   = pageItems.findIndex(it => itemId(it) === targetId);
        if (fromIdx === -1 || toIdx === -1) return;
        const reordered = [...pageItems];
        const [moved] = reordered.splice(fromIdx, 1);
        reordered.splice(toIdx, 0, moved);
        const newRanking: Record<string, number> = {};
        reordered.forEach((it, idx) => { const id = itemId(it); if (id) newRanking[id] = idx; });
        ranking = newRanking;
        saveRankingToStorage(newRanking);
        draggedId = null;
        dragOverId = null;
    }

    // ── Tag colors ─────────────────────────────────────────────────────────────
    const TAG_COLORS = [
        'bg-blue-50 text-blue-600 border-blue-200',
        'bg-indigo-50 text-indigo-600 border-indigo-200',
        'bg-violet-50 text-violet-600 border-violet-200',
        'bg-purple-50 text-purple-600 border-purple-200',
        'bg-pink-50 text-pink-600 border-pink-200',
        'bg-rose-50 text-rose-600 border-rose-200',
        'bg-orange-50 text-orange-600 border-orange-200',
        'bg-amber-50 text-amber-600 border-amber-200',
        'bg-yellow-50 text-yellow-600 border-yellow-200',
        'bg-lime-50 text-lime-600 border-lime-200',
        'bg-green-50 text-green-600 border-green-200',
        'bg-emerald-50 text-emerald-600 border-emerald-200',
        'bg-teal-50 text-teal-600 border-teal-200',
        'bg-cyan-50 text-cyan-600 border-cyan-200',
        'bg-sky-50 text-sky-600 border-sky-200',
    ];

    function tagColorClass(tag: string): string {
        let hash = 0;
        for (let i = 0; i < tag.length; i++) hash = (hash * 31 + tag.charCodeAt(i)) & 0xffff;
        return TAG_COLORS[hash % TAG_COLORS.length];
    }

    // ── Sectioned list helpers ─────────────────────────────────────────────────
    let isSectioned = $derived(origin === 'welcome' || items.some(
        (it) => typeof it === 'object' && it !== null && 'status' in (it as Record<string, unknown>)
    ));

    const STATUS_MAP: Record<string, string> = {
        posts: 'published',
        drafts: 'draft',
    };

    const HEADING_MAP: Record<string, string> = {
        posts: 'Your Posts',
        drafts: 'Your Drafts',
    };

    const EMPTY_MAP: Record<string, string> = {
        posts: 'No published posts yet',
        drafts: 'No drafts yet',
    };

    function matchesSearch(item: unknown, query: string): boolean {
        if (!query) return true;
        const q = query.toLowerCase();
        return itemLabel(item).toLowerCase().includes(q) || getPreview(item).toLowerCase().includes(q);
    }

    function getDateValue(item: unknown): number {
        if (typeof item !== 'object' || item === null) return 0;
        const o = item as Record<string, unknown>;
        const d = (o.created_at || o.published_at || o.updated_at || '') as string;
        return d ? new Date(d).getTime() : 0;
    }

    function getPublishedDate(item: unknown): string {
        if (typeof item !== 'object' || item === null) return '';
        const o = item as Record<string, unknown>;
        const d = (o.created_at || o.published_at || o.updated_at || '') as string;
        if (!d) return '';
        try {
            return new Date(d).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
        } catch { return d; }
    }

    let filteredItems = $derived(
        !isSectioned ? [] :
        $activePage === 'tags'
            ? items.filter(it => getTags(it).includes($activeTag))
            : items.filter(it => getField(it, 'status') === (STATUS_MAP[$activePage] ?? ''))
    );

    let pageItems = $derived(
        [...filteredItems]
            .filter(it => matchesSearch(it, $searchQuery))
            .sort((a, b) => {
                if ($activePage === 'posts') return getDateValue(b) - getDateValue(a);
                if ($activePage === 'drafts') {
                    const ra = getItemRank(a), rb = getItemRank(b);
                    if (ra !== rb) return ra - rb;
                    return itemLabel(a).localeCompare(itemLabel(b));
                }
                return 0;
            })
    );

    // ── Item accessors ─────────────────────────────────────────────────────────
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

    function getPreview(item: unknown): string {
        if (typeof item === 'object' && item !== null) {
            const r = item as Record<string, unknown>;
            return (r.preview as string) || (r.snippet as string) || '';
        }
        return '';
    }

    function getMetadata(item: unknown): Record<string, unknown> {
        if (typeof item === 'object' && item !== null)
            return ((item as Record<string, unknown>).metadata as Record<string, unknown>) || {};
        return {};
    }

    function getTags(item: unknown): string[] {
        const tags = getMetadata(item).tags;
        return Array.isArray(tags) ? (tags as string[]) : [];
    }

    function getField(item: unknown, field: string): string {
        if (typeof item === 'object' && item !== null)
            return ((item as Record<string, unknown>)[field] as string) || '';
        return '';
    }

    // ── Interactions ───────────────────────────────────────────────────────────
    function handleClick(item: unknown) {
        const id = itemId(item);
        if (!id) return;
        if (expandedIds.has(id)) {
            expandedIds.delete(id);
            expandedIds = new Set(expandedIds);
        } else {
            expandedIds.add(id);
            expandedIds = new Set(expandedIds);
            conversation.selectPost(id);
        }
    }

    function handleViewPost(id: string) {
        conversation.viewPost(id);
        expandPost();
    }

    const CREATE_PAGES = new Set(['drafts']);

    const VIEW_LABEL: Record<string, string> = {
        published: 'View Full Post',
        draft: 'View Full Draft',
        note: 'View Full Note',
    };

    function getViewLabel(item: unknown): string {
        return VIEW_LABEL[getField(item, 'status')] || 'View Full Post';
    }

    // ── Tag editing ────────────────────────────────────────────────────────────
    let addingTagId: string | null = $state(null);
    let newTagInput = $state('');

    function handleAddTag(item: unknown) {
        const id = itemId(item);
        const tag = newTagInput.trim();
        if (id && tag) {
            const tags = getTags(item);
            if (!tags.includes(tag)) conversation.updatePost(id, { tags: [...tags, tag] });
        }
        addingTagId = null;
        newTagInput = '';
    }

    function handleRemoveTag(item: unknown, tag: string) {
        const id = itemId(item);
        if (!id) return;
        conversation.updatePost(id, { tags: getTags(item).filter(t => t !== tag) });
    }
</script>

{#snippet itemRow(item: unknown, i: number)}
    {@const id = itemId(item)}
    {@const clickable = !!id}
    {@const expanded = id !== null && expandedIds.has(id)}
    {@const isDraggable = $activePage === 'drafts' && !!id}
    {@const isPost = getField(item, 'status') === 'published'}
    <div
        class="rounded {expanded ? 'bg-[var(--surface)] border border-[var(--border)] mb-2' : ''} {dragOverId === id ? 'border-t-2 border-[var(--accent)]' : ''}"
        draggable={isDraggable}
        ondragstart={(e) => { if (isDraggable && id) { draggedId = id; e.dataTransfer?.setData('text', id); } }}
        ondragover={(e) => { e.preventDefault(); if (isDraggable && id) dragOverId = id; }}
        ondrop={(e) => { e.preventDefault(); handleDrop(id); }}
        ondragend={() => { draggedId = null; dragOverId = null; }}
    >
        <div
            class="group flex items-center gap-2 py-2 px-2 rounded {clickable ? 'cursor-pointer' : ''}"
            onclick={() => handleClick(item)}
            role={clickable ? 'button' : undefined}
            tabindex={clickable ? 0 : undefined}
            onkeydown={(e) => { if (clickable && e.key === 'Enter') handleClick(item); }}
        >
            {#if isDraggable}
                <span class="opacity-0 group-hover:opacity-100 transition-opacity cursor-grab text-[var(--muted)] shrink-0 select-none">
                    <IconGripVertical size={14} />
                </span>
            {/if}
            {#if ordered}
                <span class="text-[var(--muted)] w-5 shrink-0 text-right">{i + 1}.</span>
            {/if}
            <span class="font-semibold flex-1 {clickable ? 'group-hover:underline transition-colors' : ''} {expanded ? 'text-[var(--accent)]' : ''}">
                {itemLabel(item)}
            </span>
            {#if isPost}
                <span class="text-xs text-[var(--muted)] shrink-0 ml-auto {clickable ? 'group-hover:underline' : ''}">
                    {getPublishedDate(item)}
                </span>
            {/if}
        </div>

        {#if expanded}
            <div class="px-4 pb-3 pt-1 space-y-2 border-t border-[var(--border)] ml-4 mr-2">
                <div class="group/tags flex flex-wrap gap-1.5 items-center">
                    {#each getTags(item) as tag}
                        <button
                            class="inline-block text-[0.65rem] leading-none py-[3px] px-2 border rounded-full font-medium {tagColorClass(tag)} cursor-pointer"
                            onclick={(e) => { e.stopPropagation(); showTagPage(tag); }}
                            title="View all posts tagged '{tag}'"
                        >{tag}</button>
                    {/each}
                    {#if addingTagId === id}
                        <input
                            class="text-[0.65rem] py-[3px] px-2 border border-dashed rounded-full outline-none bg-transparent text-[var(--text)] placeholder-[var(--muted)] w-20"
                            placeholder="new tag"
                            bind:value={newTagInput}
                            onblur={() => handleAddTag(item)}
                            onkeydown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleAddTag(item); } else if (e.key === 'Escape') { addingTagId = null; newTagInput = ''; } }}
                            autofocus
                        />
                    {:else}
                        <button
                            class="opacity-0 group-hover/tags:opacity-100 transition-opacity text-[0.65rem] leading-none py-[3px] px-2 border border-dashed rounded-full text-[var(--muted)] cursor-pointer hover:text-[var(--accent)] hover:border-[var(--accent)]"
                            onclick={(e) => { e.stopPropagation(); addingTagId = id; newTagInput = ''; }}
                            title="Add tag"
                        >+ tag</button>
                    {/if}
                </div>

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
                    {#if $activePage === 'tags'}
                        <button
                            class="text-xs text-[var(--muted)] hover:text-red-500 cursor-pointer transition-colors"
                            onclick={(e) => { e.stopPropagation(); handleRemoveTag(item, $activeTag); }}
                        >Remove Tag</button>
                    {:else if getField(item, 'status') === 'draft'}
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
    {#if $activePage === 'tags'}
        <!-- Tags page -->
        <div class="px-2 relative">
            <div class="flex items-center gap-2 mb-4">
                <button
                    onclick={goBack}
                    class="text-[var(--muted)] hover:text-[var(--accent)] cursor-pointer transition-colors shrink-0"
                    title="Back"
                >
                    <IconArrowUturnLeft size={16} />
                </button>
                <h2 class="text-lg font-semibold text-[var(--secondary)] flex-1 text-center">
                    <span class="inline-block text-[0.65rem] leading-none py-[3px] px-2 border rounded-full font-medium {tagColorClass($activeTag)} text-sm px-3 py-0.5">{$activeTag}</span>
                </h2>
            </div>
            {#if pageItems.length > 0}
                <div class="space-y-1 text-base px-2">
                    {#each pageItems as item, i}
                        {@render itemRow(item, i)}
                    {/each}
                </div>
            {:else}
                <p class="text-sm text-[var(--muted)] text-center">No posts tagged "{$activeTag}"</p>
            {/if}
        </div>
    {:else}
        <!-- Normal pages: posts / drafts -->
        <div class="px-2 relative">
            <div class="relative flex items-center justify-center mb-4">
                <button
                    onclick={expandList}
                    class="text-lg font-semibold underline text-[var(--secondary)] cursor-pointer hover:text-[var(--accent)] transition-colors"
                >{HEADING_MAP[$activePage]}</button>
                {#if $searchQuery}
                    <button
                        onclick={() => searchQuery.set('')}
                        class="absolute right-0 text-[var(--muted)] hover:text-[var(--accent)] cursor-pointer transition-colors"
                        title="Clear filter"
                    ><IconFunnel size={14} /></button>
                {/if}
            </div>
            {#if pageItems.length > 0}
                <div class="space-y-1 text-base px-2">
                    {#each pageItems as item, i}
                        <div class="group">
                            {@render itemRow(item, i)}
                        </div>
                    {/each}
                </div>
            {:else}
                <p class="text-sm text-[var(--muted)] text-center">{EMPTY_MAP[$activePage] ?? ''}</p>
            {/if}
            {#if CREATE_PAGES.has($activePage)}
                <div class="flex justify-center mt-4">
                    <button class="inline-flex items-center gap-1 py-1.5 px-4 text-sm font-medium text-[var(--accent)] border border-[var(--accent)] rounded-md bg-transparent cursor-pointer transition-colors hover:bg-[var(--accent)] hover:text-[var(--bg)]" onclick={() => creatingPost.set(true)}>
                        + New Draft
                    </button>
                </div>
            {/if}
        </div>
    {/if}
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
    <div class="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onclick={() => confirmDeleteItem = null} role="presentation">
        <div class="bg-[var(--surface)] border border-[var(--border)] rounded-lg py-5 px-6 max-w-xs w-[90%] shadow-lg" onclick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
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
                            expandedIds.delete(id); expandedIds = new Set(expandedIds);
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
