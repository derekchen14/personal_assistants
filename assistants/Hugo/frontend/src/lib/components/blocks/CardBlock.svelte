<script lang="ts">
    import { md } from '$lib/utils/markdown';
    import { conversation } from '$lib/stores/conversation';
    import { displayLayout, expandPost, collapsePost } from '$lib/stores/display';
    import { onDestroy } from 'svelte';
    import IconArrowsPointingOut from '$lib/assets/IconArrowsPointingOut.svelte';
    import IconArrowsPointingIn from '$lib/assets/IconArrowsPointingIn.svelte';
    import IconSave from '$lib/assets/IconSave.svelte';

    let { data }: { data: Record<string, unknown> } = $props();

    let postId = $derived((data.post_id as string) || '');
    let title = $derived((data.title as string) || '');
    let status = $derived((data.status as string) || '');
    let content = $derived((data.content as string) || '');
    let fields = $derived((data.fields as Record<string, unknown>) || {});

    let editable = $derived(!!postId && status !== 'published');

    // Local edit state — seeded from data, diverges on user input
    let editTitle = $state('');
    let editContent = $state('');
    let dirty = $state(false);
    let autosaveTimer: ReturnType<typeof setTimeout> | null = null;

    const AUTOSAVE_MS = 60_000;

    // Re-seed local state when data changes (new post loaded or save response)
    $effect(() => {
        editTitle = title;
        editContent = content;
        dirty = false;
        clearTimer();
    });

    function clearTimer() {
        if (autosaveTimer) {
            clearTimeout(autosaveTimer);
            autosaveTimer = null;
        }
    }

    function resetTimer() {
        clearTimer();
        autosaveTimer = setTimeout(save, AUTOSAVE_MS);
    }

    function onInput() {
        dirty = true;
        resetTimer();
    }

    function save() {
        clearTimer();
        if (!postId || !dirty) return;
        const updates: Record<string, unknown> = {};
        if (editTitle !== title) updates.title = editTitle;
        if (editContent !== content) updates.content = editContent;
        if (Object.keys(updates).length > 0) {
            conversation.updatePost(postId, updates);
        }
        dirty = false;
    }

    onDestroy(() => {
        // Flush pending changes when component unmounts
        if (dirty && postId) save();
        clearTimer();
    });
</script>

<div class="card-root">
    <!-- Top-right icon row -->
    <div class="absolute top-4 right-4 flex items-center gap-2 z-10">
        {#if editable && dirty}
            <button
                onclick={save}
                class="text-[var(--muted)] hover:text-[var(--accent)] cursor-pointer transition-colors"
                title="Save"
            >
                <IconSave size={18} />
            </button>
        {/if}
        <button
            onclick={() => $displayLayout === 'split' ? expandPost() : collapsePost()}
            class="text-[var(--muted)] hover:text-[var(--accent)] cursor-pointer transition-colors"
            title={$displayLayout === 'split' ? 'Expand' : 'Collapse'}
        >
            {#if $displayLayout === 'split'}
                <IconArrowsPointingOut size={18} />
            {:else}
                <IconArrowsPointingIn size={18} />
            {/if}
        </button>
    </div>

    {#if editable}
        <!-- Inline-editable draft/note -->
        <input
            type="text"
            bind:value={editTitle}
            oninput={onInput}
            class="text-lg font-semibold bg-transparent text-[var(--secondary)] outline-none border-b border-transparent focus:border-[var(--accent)] transition-colors pr-16 shrink-0"
            placeholder="Title"
        />
        <textarea
            bind:value={editContent}
            oninput={onInput}
            class="edit-textarea"
            placeholder="Start writing..."
        ></textarea>
    {:else}
        <!-- Read-only published post -->
        {#if title}
            <h3 class="text-lg font-semibold mb-4 text-[var(--secondary)] pr-16 shrink-0">{title}</h3>
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
            <div class="prose-content text-sm leading-relaxed flex-1 overflow-y-auto">{@html md(content)}</div>
        {/if}
    {/if}
</div>

<style>
    .card-root {
        display: flex;
        flex-direction: column;
        flex: 1;
        padding: 1.5rem;
        position: relative;
        min-height: 0;
    }
    .edit-textarea {
        flex: 1;
        min-height: 0;
        padding: 0.5rem 0;
        border: none;
        background: transparent;
        color: var(--text);
        font-size: 0.875rem;
        line-height: 1.7;
        resize: none;
        outline: none;
    }
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
