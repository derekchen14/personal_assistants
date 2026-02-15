<script lang="ts">
    let { data }: { data: Record<string, unknown> } = $props();

    let rows = $derived((data.rows as Record<string, unknown>[]) || []);
    let columns = $derived((data.columns as string[]) || (rows.length > 0 ? Object.keys(rows[0]) : []));
    let title = $derived((data.title as string) || '');
</script>

{#if title}
    <h3 class="text-sm font-medium mb-3">{title}</h3>
{/if}

<div class="overflow-x-auto rounded-lg border border-[var(--color-border)]">
    <table class="w-full text-sm">
        <thead>
            <tr class="bg-[var(--color-surface)]">
                {#each columns as col}
                    <th class="px-3 py-2 text-left font-medium text-[var(--color-text-muted)] border-b border-[var(--color-border)]">
                        {col}
                    </th>
                {/each}
            </tr>
        </thead>
        <tbody>
            {#each rows as row, i}
                <tr class="hover:bg-[var(--color-surface-hover)]" class:border-b={i < rows.length - 1} class:border-[var(--color-border)]={i < rows.length - 1}>
                    {#each columns as col}
                        <td class="px-3 py-2">{String(row[col] ?? '')}</td>
                    {/each}
                </tr>
            {/each}
        </tbody>
    </table>
</div>
