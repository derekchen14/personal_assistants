<script lang="ts">
    import { md } from '$lib/utils/markdown';

    let { data }: { data: Record<string, unknown> } = $props();

    let items = $derived((data.items as unknown[]) || []);
    let title = $derived((data.title as string) || '');
    let content = $derived((data.content as string) || '');
    let ordered = $derived((data.ordered as boolean) || false);

    function itemLabel(item: unknown): string {
        if (typeof item === 'string') return item;
        if (typeof item === 'object' && item !== null) {
            const o = item as Record<string, unknown>;
            const label = (o.title || o.name || o.display_name || '') as string;
            const status = o.status ? ` · ${o.status}` : '';
            const category = o.category ? ` · ${o.category}` : '';
            return `**${label}**${status}${category}`;
        }
        return String(item);
    }
</script>

{#if title}
    <h3 class="text-sm font-medium mb-3">{title}</h3>
{/if}

{#if items.length > 0}
    <div class="space-y-1 text-sm">
        {#each items as item, i}
            <div class="flex gap-2 py-1">
                <span class="text-[var(--color-text-muted)] w-5 shrink-0 text-right">
                    {ordered ? `${i + 1}.` : '\u2022'}
                </span>
                <span>{@html md(itemLabel(item))}</span>
            </div>
        {/each}
    </div>
{:else if content}
    <div class="text-sm leading-relaxed">{@html md(content)}</div>
{/if}
