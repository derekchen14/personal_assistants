<script lang="ts">
    import { conversation } from '$lib/stores/conversation';
    import { activePage, searchQuery, creatingItem } from '$lib/stores/display';
    import { Trash } from '$lib/components/icons';

    let { data }: { data: Record<string, unknown> } = $props();

    let items = $derived((data.items as unknown[]) || []);
    let source = $derived((data.source as string) || '');
    let content = $derived((data.content as string) || '');

    let isSectioned = $derived(source === 'welcome' || items.some(
        (it) => typeof it === 'object' && it !== null && 'entity' in (it as Record<string, unknown>)
    ));

    const ENTITY_MAP: Record<string, string> = {
        assistants: 'assistant',
        requirements: 'requirement',
        tools: 'tool',
    };

    const HEADING_MAP: Record<string, string> = {
        assistants: 'Assistants',
        requirements: 'Requirements',
        tools: 'Tools',
    };

    const EMPTY_MAP: Record<string, string> = {
        assistants: 'No assistants found',
        requirements: 'No requirements yet',
        tools: 'No tools yet',
    };

    const CREATE_PAGES = new Set(['requirements', 'tools']);

    const CREATE_LABEL: Record<string, string> = {
        requirements: '+ New Requirement',
        tools: '+ New Tool',
    };

    function itemId(item: unknown): string | null {
        if (typeof item !== 'object' || item === null) return null;
        const o = item as Record<string, unknown>;
        if (o.entity === 'assistant') return (o.name as string) || null;
        if (o.entity === 'requirement') return (o.req_id as string) || null;
        if (o.entity === 'tool') return (o.tool_id as string) || null;
        return null;
    }

    function itemLabel(item: unknown): string {
        if (typeof item === 'string') return item;
        if (typeof item === 'object' && item !== null) {
            const o = item as Record<string, unknown>;
            if (o.entity === 'requirement') return (o.text as string) || '';
            return (o.name || o.title || o.display_name || '') as string;
        }
        return String(item);
    }

    function matchesSearch(item: unknown, query: string): boolean {
        if (!query) return true;
        return itemLabel(item).toLowerCase().includes(query.toLowerCase());
    }

    let pageItems = $derived(
        items
            .filter((it) => {
                if (!isSectioned) return true;
                const o = it as Record<string, unknown>;
                return o.entity === ENTITY_MAP[$activePage];
            })
            .filter((it) => matchesSearch(it, $searchQuery))
    );

    let confirmDeleteItem: unknown | null = $state(null);

    function handleClick(item: unknown) {
        const o = item as Record<string, unknown>;
        if (o.entity === 'assistant') {
            conversation.selectAssistant(o.name as string);
        } else if (o.entity === 'requirement') {
            conversation.selectRequirement(o.req_id as string);
        } else if (o.entity === 'tool') {
            conversation.selectTool(o.tool_id as string);
        }
    }

    function handleDelete(item: unknown) {
        const o = item as Record<string, unknown>;
        if (o.entity === 'requirement') {
            conversation.deleteRequirement(o.req_id as string);
        } else if (o.entity === 'tool') {
            conversation.deleteTool(o.tool_id as string);
        }
        confirmDeleteItem = null;
    }
</script>

{#if isSectioned}
    <div class="px-2">
        <h2 class="text-base font-semibold text-[var(--color-secondary)] mb-4 text-center">
            {HEADING_MAP[$activePage]}
        </h2>

        {#if pageItems.length > 0}
            <div class="space-y-1 text-sm">
                {#each pageItems as item}
                    {@const id = itemId(item)}
                    {@const isReadOnly = (item as Record<string, unknown>).entity === 'assistant'}
                    <div class="group flex items-center gap-2 py-2 px-2 rounded cursor-pointer hover:bg-[var(--color-surface)]"
                        onclick={() => handleClick(item)}
                        role="button"
                        tabindex="0"
                        onkeydown={(e) => { if (e.key === 'Enter') handleClick(item); }}
                    >
                        <span class="flex-1 font-medium group-hover:underline transition-colors">
                            {itemLabel(item)}
                        </span>
                        {#if !isReadOnly && id}
                            <button
                                class="opacity-0 group-hover:opacity-100 transition-opacity text-[var(--color-text-muted)] hover:text-red-500 cursor-pointer shrink-0"
                                title="Delete"
                                onclick={(e) => { e.stopPropagation(); confirmDeleteItem = item; }}
                            >
                                <Trash size={14} />
                            </button>
                        {/if}
                    </div>
                {/each}
            </div>
        {:else}
            <p class="text-sm text-[var(--color-text-muted)] text-center">
                {EMPTY_MAP[$activePage] ?? ''}
            </p>
        {/if}

        {#if CREATE_PAGES.has($activePage)}
            <div class="flex justify-center mt-4">
                <button
                    class="inline-flex items-center gap-1 py-1.5 px-4 text-sm font-medium text-[var(--color-accent)] border border-[var(--color-accent)] rounded-md bg-transparent cursor-pointer transition-colors hover:bg-[var(--color-accent)] hover:text-white"
                    onclick={() => creatingItem.set(true)}
                >
                    {CREATE_LABEL[$activePage]}
                </button>
            </div>
        {/if}
    </div>
{:else if items.length > 0}
    <div class="space-y-1 text-sm px-2">
        {#each items as item}
            <div class="py-1 px-2">{itemLabel(item)}</div>
        {/each}
    </div>
{:else if content}
    <div class="text-sm leading-relaxed">{content}</div>
{/if}

{#if confirmDeleteItem}
    <div
        class="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
        onclick={() => confirmDeleteItem = null}
        role="presentation"
    >
        <div
            class="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg py-5 px-6 max-w-xs w-[90%] shadow-lg"
            onclick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
        >
            <p class="text-sm font-medium mb-1">Delete "{itemLabel(confirmDeleteItem)}"?</p>
            <p class="text-xs text-[var(--color-text-muted)] mb-4">This action cannot be undone.</p>
            <div class="flex justify-end gap-2">
                <button
                    class="px-3 py-1.5 text-xs rounded border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] cursor-pointer transition-colors"
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
