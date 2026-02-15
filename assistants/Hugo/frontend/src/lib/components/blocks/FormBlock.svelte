<script lang="ts">
    import { conversation } from '$lib/stores/conversation';

    let { data }: { data: Record<string, unknown> } = $props();

    let title = $derived((data.title as string) || '');
    let fields = $derived((data.fields as { name: string; label: string; type?: string; required?: boolean }[]) || []);

    let values = $state<Record<string, string>>({});

    function handleSubmit() {
        const filled = Object.entries(values).filter(([, v]) => v.trim());
        if (filled.length === 0) return;
        const parts = filled.map(([k, v]) => `${k}: ${v}`).join(', ');
        conversation.send(parts);
        values = {};
    }
</script>

<div class="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
    {#if title}
        <h3 class="text-sm font-medium mb-3">{title}</h3>
    {/if}
    <div class="space-y-3">
        {#each fields as field}
            <div>
                <label class="block text-xs text-[var(--color-text-muted)] mb-1">
                    {field.label}{field.required ? ' *' : ''}
                </label>
                <input
                    type={field.type || 'text'}
                    bind:value={values[field.name]}
                    class="w-full px-3 py-1.5 rounded bg-[var(--color-bg)] border border-[var(--color-border)] text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-accent)]"
                />
            </div>
        {/each}
        <button
            onclick={handleSubmit}
            class="px-4 py-1.5 rounded bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] text-white text-sm transition-colors"
        >
            Submit
        </button>
    </div>
</div>
