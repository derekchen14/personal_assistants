<script lang="ts">
    import { md } from '$lib/utils/markdown';
    import { activePage, searchQuery } from '$lib/stores/display';

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
    };

    const HEADING_MAP: Record<string, string> = {
        sheets: 'Your Sheets',
        queries: 'Your Queries',
    };

    const EMPTY_MAP: Record<string, string> = {
        sheets: 'No sheets yet',
        queries: 'No saved queries yet',
    };

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

    function itemLabel(item: unknown): string {
        if (typeof item === 'string') return item;
        if (typeof item === 'object' && item !== null) {
            const o = item as Record<string, unknown>;
            return (o.title || o.name || o.display_name || '') as string;
        }
        return String(item);
    }

    function getField(item: unknown, field: string): string {
        if (typeof item === 'object' && item !== null) {
            return ((item as Record<string, unknown>)[field] as string) || '';
        }
        return '';
    }
</script>

{#if isSectioned}
    <!-- Single-page view based on active header tab -->
    <div class="px-2">
        <h2 class="text-center text-lg font-semibold underline text-[var(--secondary)] mb-4">{HEADING_MAP[$activePage]}</h2>
        {#if pageItems.length > 0}
            <div class="space-y-1 text-base px-2">
                {#each pageItems as item, i}
                    <div class="flex gap-2 py-2 px-2 rounded">
                        {#if ordered}
                            <span class="text-[var(--muted)] w-5 shrink-0 text-right">{i + 1}.</span>
                        {/if}
                        <span class="font-semibold">{itemLabel(item)}</span>
                    </div>
                {/each}
            </div>
        {:else}
            <p class="text-sm text-[var(--muted)] text-center">{EMPTY_MAP[$activePage]}</p>
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
                <span>{@html md(itemLabel(item))}</span>
            </div>
        {/each}
    </div>
{:else if content}
    <div class="text-base leading-relaxed">{@html md(content)}</div>
{/if}
