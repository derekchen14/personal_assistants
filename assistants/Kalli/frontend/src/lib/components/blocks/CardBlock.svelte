<script lang="ts">
    let { data }: { data: Record<string, unknown> } = $props();

    let title = $derived((data.title as string) || '');
    let fields = $derived((data.fields as Record<string, unknown>) || {});
</script>

<div class="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
    {#if title}
        <h3 class="text-sm font-medium mb-3">{title}</h3>
    {/if}
    <div class="space-y-2">
        {#each Object.entries(fields) as [key, value]}
            <div class="flex justify-between text-sm">
                <span class="text-[var(--color-text-muted)]">{key}</span>
                <span>{String(value)}</span>
            </div>
        {/each}
    </div>
</div>
