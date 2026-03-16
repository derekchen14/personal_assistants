<script lang="ts">
    import { md } from '$lib/utils/markdown';

    let { data }: { data: Record<string, unknown> } = $props();

    let left = $derived((data.left as Record<string, unknown>) || {});
    let right = $derived((data.right as Record<string, unknown>) || {});
    let content = $derived((data.content as string) || '');
</script>

<div class="flex flex-col flex-1 min-h-0">
    {#if content}
        <div class="px-4 py-3 border-b border-[var(--border)] bg-[var(--hover)] text-sm leading-relaxed">
            {@html md(content)}
        </div>
    {/if}

    <div class="grid grid-cols-2 gap-4 p-4 flex-1 min-h-0">
        {#each [left, right] as panel}
            <div class="flex flex-col border border-[var(--border)] rounded-lg overflow-hidden min-h-0">
                <div class="px-3 py-2 bg-[var(--hover)] border-b border-[var(--border)] shrink-0">
                    <h4 class="text-sm font-semibold text-[var(--secondary)] truncate">
                        {panel.title || 'Untitled'}
                    </h4>
                    {#if panel.status}
                        <span class="text-xs text-[var(--muted)]">{panel.status}</span>
                    {/if}
                </div>
                <div class="flex-1 overflow-y-auto p-3 text-sm leading-relaxed prose-content">
                    {@html md(String(panel.content || ''))}
                </div>
            </div>
        {/each}
    </div>
</div>

<style>
    .prose-content :global(h1) { font-size: 1.25rem; font-weight: 700; margin: 0.75rem 0 0.5rem; }
    .prose-content :global(h2) { font-size: 1.1rem; font-weight: 600; margin: 0.5rem 0 0.25rem; }
    .prose-content :global(p) { margin: 0.25rem 0; }
    .prose-content :global(ul), .prose-content :global(ol) { margin: 0.25rem 0; padding-left: 1.25rem; }
    .prose-content :global(ul) { list-style-type: disc; }
    .prose-content :global(ol) { list-style-type: decimal; }
</style>
