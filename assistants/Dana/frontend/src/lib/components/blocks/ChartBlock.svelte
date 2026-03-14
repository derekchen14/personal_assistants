<script lang="ts">
    let { data }: { data: Record<string, unknown> } = $props();

    let imageBase64 = $derived((data.image_base64 as string) || '');
    let chartType = $derived((data.chart_type as string) || 'chart');
    let title = $derived((data.title as string) || '');
    let dataset = $derived((data.dataset as string) || '');
</script>

<div class="p-4">
    {#if title}
        <h3 class="text-sm font-medium mb-3 text-[var(--secondary)]">{title}</h3>
    {/if}
    {#if imageBase64}
        <img
            src="data:image/png;base64,{imageBase64}"
            alt="{chartType} chart{dataset ? ` of ${dataset}` : ''}"
            class="w-full rounded"
        />
    {:else}
        <div class="flex items-center justify-center h-48 text-[var(--muted)] text-sm">
            Chart rendering...
        </div>
    {/if}
    {#if dataset}
        <p class="text-xs text-[var(--muted)] mt-2">Source: {dataset}</p>
    {/if}
</div>
