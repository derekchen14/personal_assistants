<script lang="ts">
    import { md } from '$lib/utils/markdown';
    import { conversation } from '$lib/stores/conversation';
    import { showChosenOutline } from '$lib/stores/display';

    interface Section { name: string; description: string; checked?: boolean }
    type Candidate = Section[];

    let { data, origin = '' }: { data: Record<string, unknown>; origin?: string } = $props();

    let candidates = $derived((data.candidates as Candidate[]) ?? []);

    function pick(idx: number) {
        const chosen = candidates[idx];
        if (!chosen) return;
        showChosenOutline(chosen);
        conversation.action(`select proposal ${idx + 1}`, '{002}', { proposals: [chosen] }, true);
    }

    function renderSections(sections: Section[]): string {
        return sections
            .map((sec) => `**${sec.name}**\n\n${sec.description || ''}`)
            .join('\n\n');
    }
</script>

<div class="flex flex-col flex-1 p-6 min-h-0">
    <h3 class="text-lg font-semibold mb-3 text-[var(--secondary)] shrink-0">
        Outline options
    </h3>
    <div class="flex-1 overflow-y-auto space-y-4">
        {#each candidates as candidate, i}
            <div class="border border-[var(--border)] rounded-lg p-4">
                <div class="flex items-center justify-between mb-2">
                    <span class="text-sm font-medium text-[var(--secondary)]">
                        Option {i + 1}
                    </span>
                    <button
                        onclick={() => pick(i)}
                        class="px-3 py-1 rounded bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white text-xs cursor-pointer transition-colors"
                    >
                        Pick
                    </button>
                </div>
                <div class="prose-content text-sm leading-relaxed">{@html md(renderSections(candidate))}</div>
            </div>
        {/each}
    </div>
</div>

<style>
    .prose-content :global(p) { margin: 0.25rem 0; }
    .prose-content :global(strong) { font-weight: 600; }
</style>
