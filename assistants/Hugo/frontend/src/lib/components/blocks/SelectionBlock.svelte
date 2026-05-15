<script lang="ts">
    import { md } from '$lib/utils/markdown';
    import { conversation } from '$lib/stores/conversation';
    import { showChosenOutline } from '$lib/stores/display';

    interface Option {
        label: string;
        dax: string;
        payload: Record<string, unknown>;
        body?: string;
    }

    let { data, origin = '' }: { data: Record<string, unknown>; origin?: string } = $props();

    let title = $derived((data.title as string) || 'Choose one');
    let options = $derived((data.options as Option[]) ?? []);

    function priorCardData(): Record<string, unknown> {
        // Walk back through agent messages to find the most recent card frame. Selections land in
        // the bottom panel and displace the prior card, so bottomFrame is no help by the time we
        // click; the conversation log is the surviving record of what was on screen before.
        const msgs = $conversation.messages;
        for (let idx = msgs.length - 1; idx >= 0; idx--) {
            const block = (msgs[idx].artifact as any)?.blocks?.[0];
            if (block?.type === 'card') return (block.data ?? {}) as Record<string, unknown>;
        }
        return {};
    }

    function pick(idx: number) {
        const opt = options[idx];
        if (!opt) return;
        const proposals = opt.payload?.proposals as Array<{ name: string; description?: string }>[] | undefined;
        if (proposals && proposals.length) {
            showChosenOutline(proposals[0], priorCardData());
        }
        conversation.action(opt.label, opt.dax, opt.payload, true);
    }
</script>

<div class="flex flex-col flex-1 p-6 min-h-0">
    <h3 class="text-lg font-semibold mb-3 text-[var(--secondary)] shrink-0">
        {title}
    </h3>
    <div class="flex-1 overflow-y-auto space-y-4">
        {#each options as opt, i}
            <div class="border border-[var(--border)] rounded-lg p-4">
                <div class="flex items-center justify-between mb-2">
                    <span class="text-sm font-medium text-[var(--secondary)]">
                        {opt.label}
                    </span>
                    <button
                        onclick={() => pick(i)}
                        class="px-3 py-1 rounded bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white text-xs cursor-pointer transition-colors"
                    >
                        Pick
                    </button>
                </div>
                {#if opt.body}
                    <div class="prose-content text-sm leading-relaxed">{@html md(opt.body)}</div>
                {/if}
            </div>
        {/each}
    </div>
</div>

<style>
    .prose-content :global(p) { margin: 0.25rem 0; }
    .prose-content :global(strong) { font-weight: 600; }
</style>
