<script lang="ts">
    import { md } from '$lib/utils/markdown';
    import { displayLayout, expandPost, collapsePost } from '$lib/stores/display';
    import IconArrowsPointingOut from '$lib/assets/IconArrowsPointingOut.svelte';
    import IconArrowsPointingIn from '$lib/assets/IconArrowsPointingIn.svelte';

    let { data }: { data: Record<string, unknown> } = $props();

    let title = $derived((data.title as string) || '');
    let content = $derived((data.content as string) || '');
    let fields = $derived((data.fields as Record<string, unknown>) || {});
</script>

<div class="p-6 flex-1 relative">
    {#if content}
        <button
            onclick={() => $displayLayout === 'split' ? expandPost() : collapsePost()}
            class="absolute top-4 right-4 text-[var(--muted)] hover:text-[var(--accent)] cursor-pointer transition-colors"
            title={$displayLayout === 'split' ? 'Expand' : 'Collapse'}
        >
            {#if $displayLayout === 'split'}
                <IconArrowsPointingOut size={18} />
            {:else}
                <IconArrowsPointingIn size={18} />
            {/if}
        </button>
    {/if}
    {#if title}
        <h3 class="text-lg font-semibold mb-4 text-[var(--secondary)] pr-8">{title}</h3>
    {/if}
    {#if Object.keys(fields).length > 0}
        <div class="space-y-2">
            {#each Object.entries(fields) as [key, value]}
                <div class="flex justify-between text-sm">
                    <span class="text-[var(--muted)]">{key}</span>
                    <span>{String(value)}</span>
                </div>
            {/each}
        </div>
    {:else if content}
        <div class="prose-content text-sm leading-relaxed">{@html md(content)}</div>
    {/if}
</div>

<style>
    .prose-content :global(h1) { font-size: 1.5rem; font-weight: 700; margin: 1.25rem 0 0.75rem; }
    .prose-content :global(h2) { font-size: 1.25rem; font-weight: 600; margin: 1rem 0 0.5rem; }
    .prose-content :global(h3) { font-size: 1.1rem; font-weight: 600; margin: 0.75rem 0 0.5rem; }
    .prose-content :global(p) { margin: 0.5rem 0; }
    .prose-content :global(ul), .prose-content :global(ol) { margin: 0.5rem 0; padding-left: 1.5rem; }
    .prose-content :global(ul) { list-style-type: disc; }
    .prose-content :global(ol) { list-style-type: decimal; }
    .prose-content :global(li) { margin: 0.25rem 0; }
    .prose-content :global(blockquote) {
        border-left: 3px solid var(--border);
        padding-left: 1rem;
        margin: 0.75rem 0;
        color: var(--muted);
    }
    .prose-content :global(code) {
        font-size: 0.85em;
        background: var(--hover, #e5e5e5);
        padding: 0.15rem 0.35rem;
        border-radius: 3px;
    }
    .prose-content :global(pre) {
        background: var(--hover, #e5e5e5);
        padding: 0.75rem 1rem;
        border-radius: 6px;
        overflow-x: auto;
        margin: 0.75rem 0;
    }
    .prose-content :global(pre code) {
        background: none;
        padding: 0;
    }
    .prose-content :global(a) {
        color: var(--accent);
        text-decoration: underline;
    }
    .prose-content :global(hr) {
        border: none;
        border-top: 1px solid var(--border);
        margin: 1rem 0;
    }
    .prose-content :global(table) {
        width: 100%;
        border-collapse: collapse;
        margin: 0.75rem 0;
    }
    .prose-content :global(th), .prose-content :global(td) {
        border: 1px solid var(--border);
        padding: 0.35rem 0.75rem;
        text-align: left;
    }
    .prose-content :global(th) {
        font-weight: 600;
        background: var(--hover, #e5e5e5);
    }
</style>
