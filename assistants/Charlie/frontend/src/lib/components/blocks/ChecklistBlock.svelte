<script lang="ts">
    import { md } from '$lib/utils/markdown';
    import { conversation } from '$lib/stores/conversation';

    interface Option {
        label: string;
        payload: unknown;
        body?: string;
    }

    let { data }: { data: Record<string, unknown> } = $props();

    let title = $derived((data.title as string) || 'Choose any');
    let options = $derived((data.options as Option[]) ?? []);
    let submitDax = $derived((data.submit_dax as string) || '');
    let submitLabel = $derived((data.submit_label as string) || 'Submit');

    let selected = $state<Set<number>>(new Set());

    function toggle(idx: number) {
        const next = new Set(selected);
        if (next.has(idx)) next.delete(idx);
        else next.add(idx);
        selected = next;
    }

    function submit() {
        const items = [...selected].sort((a, b) => a - b).map(i => options[i].payload);
        conversation.action(submitLabel, submitDax, { choices: items }, true);
    }
</script>

<div class="flex flex-col flex-1 p-6 min-h-0">
    <h3 class="text-lg font-semibold mb-3 text-[var(--secondary)] shrink-0">
        {title}
    </h3>
    <div class="flex-1 overflow-y-auto space-y-4">
        {#each options as opt, i}
            <label class="block border border-[var(--border)] rounded-lg p-4 cursor-pointer hover:bg-[var(--hover)]">
                <div class="flex items-start gap-3 mb-2">
                    <input
                        type="checkbox"
                        checked={selected.has(i)}
                        onchange={() => toggle(i)}
                        class="mt-0.5 cursor-pointer"
                    />
                    <span class="text-sm font-medium text-[var(--secondary)]">
                        {opt.label}
                    </span>
                </div>
                {#if opt.body}
                    <div class="prose-content text-sm leading-relaxed pl-7">{@html md(opt.body)}</div>
                {/if}
            </label>
        {/each}
    </div>
    <div class="shrink-0 mt-4 flex justify-end">
        <button
            onclick={submit}
            disabled={selected.size === 0}
            class="px-4 py-1.5 rounded bg-[var(--accent)] hover:bg-[var(--accent-dark)] disabled:bg-[var(--border)] disabled:cursor-not-allowed text-white text-sm cursor-pointer transition-colors"
        >
            {submitLabel} ({selected.size})
        </button>
    </div>
</div>

<style>
    .prose-content :global(p) { margin: 0.25rem 0; }
    .prose-content :global(strong) { font-weight: 600; }
</style>
