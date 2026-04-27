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

<div class="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
    {#if title}
        <h3 class="text-sm font-medium mb-3">{title}</h3>
    {/if}
    <div class="space-y-3">
        {#each fields as field}
            <label class="block">
                <span class="block text-xs text-[var(--muted)] mb-1">
                    {field.label}{field.required ? ' *' : ''}
                </span>
                <input
                    type={field.type || 'text'}
                    bind:value={values[field.name]}
                    class="w-full px-3 py-1.5 rounded bg-[var(--bg)] border border-[var(--border)] text-sm text-[var(--text)] outline-none focus:border-[var(--accent)]"
                />
            </label>
        {/each}
        <button
            onclick={handleSubmit}
            class="px-4 py-1.5 rounded bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white text-sm transition-colors"
        >
            Submit
        </button>
    </div>
</div>
