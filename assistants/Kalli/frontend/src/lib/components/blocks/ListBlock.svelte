<script lang="ts">
    let { data }: { data: Record<string, unknown> } = $props();

    let items = $derived((data.items as string[]) || []);
    let title = $derived((data.title as string) || '');
    let ordered = $derived((data.ordered as boolean) || false);
</script>

{#if title}
    <h3 class="text-sm font-medium mb-3">{title}</h3>
{/if}

<div class="space-y-1 text-sm">
    {#each items as item, i}
        <div class="flex gap-2 py-1">
            <span class="text-[var(--color-text-muted)] w-5 shrink-0 text-right">
                {ordered ? `${i + 1}.` : '\u2022'}
            </span>
            <span>{item}</span>
        </div>
    {/each}
</div>
