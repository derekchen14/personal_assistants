<script lang="ts">
    import { conversation } from '$lib/stores/conversation';
    import { activePage, searchQuery, creatingItem } from '$lib/stores/display';
    import IconTrash from '$lib/assets/IconTrash.svelte';

    let { data }: { data: Record<string, unknown> } = $props();

    let items = $derived((data.items as unknown[]) || []);
    let title = $derived((data.title as string) || '');
    let content = $derived((data.content as string) || '');
    let ordered = $derived((data.ordered as boolean) || false);
    let source = $derived((data.source as string) || '');

    let isSectioned = $derived(source === 'welcome' || items.some(
        (it) => typeof it === 'object' && it !== null && 'entity' in (it as Record<string, unknown>)
    ));

    const ENTITY_MAP: Record<string, string> = {
        sheets: 'sheet',
        queries: 'query',
        metrics: 'metric',
    };

    const HEADING_MAP: Record<string, string> = {
        sheets: 'Your Sheets',
        queries: 'Your Queries',
        metrics: 'Your Metrics',
    };

    const EMPTY_MAP: Record<string, string> = {
        sheets: 'No sheets yet',
        queries: 'No saved queries yet',
        metrics: 'No metrics defined yet',
    };

    const CREATE_PAGES = new Set(['queries', 'metrics']);

    const CREATE_LABEL: Record<string, string> = {
        queries: '+ New Query',
        metrics: '+ New Metric',
    };

    function itemId(item: unknown): string | null {
        if (typeof item !== 'object' || item === null) return null;
        const o = item as Record<string, unknown>;
        if (o.entity === 'sheet') return (o.name as string) || null;
        if (o.entity === 'query') return (o.query_id as string) || null;
        if (o.entity === 'metric') return (o.metric_id as string) || null;
        return null;
    }

    function itemLabel(item: unknown): string {
        if (typeof item === 'string') return item;
        if (typeof item === 'object' && item !== null) {
            const o = item as Record<string, unknown>;
            if (o.entity === 'query') {
                const text = (o.text as string) || '';
                return text.length > 60 ? text.slice(0, 60) + '…' : text;
            }
            return (o.name || o.title || o.display_name || '') as string;
        }
        return String(item);
    }

    function matchesSearch(item: unknown, query: string): boolean {
        if (!query) return true;
        const q = query.toLowerCase();
        return itemLabel(item).toLowerCase().includes(q);
    }

    let pageItems = $derived(
        isSectioned
            ? items
                .filter((it) => getField(it, 'entity') === ENTITY_MAP[$activePage])
                .filter((it) => matchesSearch(it, $searchQuery))
            : []
    );

    function getField(item: unknown, field: string): string {
        if (typeof item === 'object' && item !== null) {
            return ((item as Record<string, unknown>)[field] as string) || '';
        }
        return '';
    }

    let confirmDeleteItem: unknown | null = $state(null);

    function handleClick(item: unknown) {
        const o = item as Record<string, unknown>;
        if (o.entity === 'sheet') {
            conversation.selectSheet(o.name as string);
        } else if (o.entity === 'query') {
            conversation.selectQuery(o.query_id as string);
        } else if (o.entity === 'metric') {
            conversation.selectMetric(o.metric_id as string);
        }
    }

    function handleDelete(item: unknown) {
        const o = item as Record<string, unknown>;
        if (o.entity === 'query') {
            conversation.deleteQuery(o.query_id as string);
        } else if (o.entity === 'metric') {
            conversation.deleteMetric(o.metric_id as string);
        }
        confirmDeleteItem = null;
    }
</script>

{#if isSectioned}
    <div class="px-2">
        <h2 class="text-center text-lg font-semibold underline text-[var(--secondary)] mb-4">{HEADING_MAP[$activePage]}</h2>
        {#if pageItems.length > 0}
            <div class="space-y-1 text-base px-2">
                {#each pageItems as item}
                    {@const id = itemId(item)}
                    {@const isReadOnly = (item as Record<string, unknown>).entity === 'sheet'}
                    <div
                        class="group flex items-center gap-2 py-2 px-2 rounded cursor-pointer hover:bg-[var(--hover)]"
                        onclick={() => handleClick(item)}
                        role="button"
                        tabindex="0"
                        onkeydown={(e) => { if (e.key === 'Enter') handleClick(item); }}
                    >
                        {#if ordered}
                            <span class="text-[var(--muted)] w-5 shrink-0 text-right">{pageItems.indexOf(item) + 1}.</span>
                        {/if}
                        <span class="flex-1 font-semibold group-hover:underline">{itemLabel(item)}</span>
                        {#if !isReadOnly && id}
                            <button
                                class="opacity-0 group-hover:opacity-100 transition-opacity text-[var(--muted)] hover:text-red-500 cursor-pointer shrink-0"
                                title="Delete"
                                onclick={(e) => { e.stopPropagation(); confirmDeleteItem = item; }}
                            >
                                <IconTrash size={14} />
                            </button>
                        {/if}
                    </div>
                {/each}
            </div>
        {:else}
            <p class="text-sm text-[var(--muted)] text-center">{EMPTY_MAP[$activePage]}</p>
        {/if}

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
    <!-- Flat list (non-sectioned) -->
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
