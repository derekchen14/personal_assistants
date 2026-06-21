<script lang="ts">
    import { md } from '$lib/utils/markdown';
    import { conversation } from '$lib/stores/conversation';

    let { data }: { data: Record<string, unknown> } = $props();

    let left = $derived((data.left as Record<string, unknown>) || {});
    let right = $derived((data.right as Record<string, unknown>) || {});
    let content = $derived((data.content as string) || '');
</script>

<div class="flex flex-col flex-1 min-h-0 rounded-lg overflow-hidden">
    {#if content}
        <div class="px-4 py-3 border-b border-[var(--border)] bg-[var(--hover)] text-sm leading-relaxed">
            {@html md(content)}
        </div>
    {/if}

    <div class="grid grid-cols-2 divide-x divide-[var(--border)] flex-1 min-h-0">
        {#each [left, right] as post}
            <div class="flex flex-col overflow-hidden min-h-0">
                <div class="px-4 py-2 bg-[var(--hover)] border-b border-[var(--border)] shrink-0">
                    {#if post.post_id}
                        <button
                            onclick={() => conversation.viewPost(String(post.post_id))}
                            class="text-sm font-semibold text-[var(--secondary)] hover:text-[var(--accent)] truncate cursor-pointer transition-colors text-left w-full"
                            title="Open this post"
                        >
                            {post.title || 'Untitled'}
                        </button>
                    {:else}
                        <h4 class="text-sm font-semibold text-[var(--secondary)] truncate">
                            {post.title || 'Untitled'}
                        </h4>
                    {/if}
                    {#if post.status}
                        <span class="text-xs text-[var(--muted)]">{post.status}</span>
                    {/if}
                </div>
                <div class="flex-1 overflow-y-auto px-4 py-3 text-sm leading-relaxed prose-content">
                    {@html md(String(post.content || ''))}
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
