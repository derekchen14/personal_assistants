<script lang="ts">
    import { md } from '$lib/utils/markdown';
    import { conversation } from '$lib/stores/conversation';
    import { displayLayout, expandPost, collapsePost, activeHighlight, activeSection } from '$lib/stores/display';
    import { onDestroy } from 'svelte';
    import IconArrowsPointingOut from '$lib/assets/IconArrowsPointingOut.svelte';
    import IconArrowsPointingIn from '$lib/assets/IconArrowsPointingIn.svelte';
    import IconDocumentCheck from '$lib/assets/IconDocumentCheck.svelte';
    import IconPencilSquare from '$lib/assets/IconPencilSquare.svelte';
    import IconLink from '$lib/assets/IconLink.svelte';
    import IconChevronRight from '$lib/assets/IconChevronRight.svelte';
    import IconBarsArrowUp from '$lib/assets/IconBarsArrowUp.svelte';
    import IconBarsArrowDown from '$lib/assets/IconBarsArrowDown.svelte';

    let { data, origin = '' }: { data: Record<string, unknown>; origin?: string } = $props();

    let postId = $derived((data.post_id as string) || '');
    let title = $derived((data.title as string) || '');
    let status = $derived((data.status as string) || '');
    let content = $derived((data.content as string) || '');
    let fields = $derived((data.fields as Record<string, unknown>) || {});
    let linkedPost = $derived((data.linked_post as Record<string, unknown>) || null);
    let pending = $derived(Boolean(data.pending));
    let sectionIds = $derived((data.section_ids as string[]) || []);

    // Edit mode: notes and newly created drafts start editable
    let editingEnabled = $state(false);
    let lastPostId = $state('');
    $effect(() => {
        if (postId !== lastPostId) {
            lastPostId = postId;
            editingEnabled = status === 'note' || origin === 'create';
            clearMark();
            activeHighlight.set('');
            activeSection.set('');
        }
    });

    let editable = $derived(editingEnabled && !!postId && status !== 'published');

    function enterEditMode() {
        if (postId && status !== 'published') editingEnabled = true;
    }

    // Persistent text highlight for view mode
    let proseEl: HTMLElement | null = null;
    let markEl: HTMLElement | null = null;

    function clearMark() {
        if (markEl) {
            const parent = markEl.parentNode;
            if (parent) {
                while (markEl.firstChild) parent.insertBefore(markEl.firstChild, markEl);
                parent.removeChild(markEl);
            }
            markEl = null;
        }
    }

    function focusOnMount(el: HTMLElement, enabled: boolean) {
        if (enabled) setTimeout(() => { el.focus(); }, 0);
    }

    function findSectionFromRange(startNode: Node): string {
        // Walk upward from the selection's startContainer to find the nearest
        // preceding <h2>. Map its text to a section title, then sectionIds[idx].
        let node: Node | null = startNode;
        while (node && node !== proseEl) {
            let sib: Node | null = node.previousSibling;
            while (sib) {
                if (sib.nodeType === Node.ELEMENT_NODE && (sib as Element).tagName === 'H2') {
                    const title = (sib.textContent || '').trim();
                    const idx = sections.findIndex(s => s.title === title);
                    return idx >= 0 ? (sectionIds[idx] ?? '') : '';
                }
                sib = sib.previousSibling;
            }
            node = node.parentNode;
        }
        return '';
    }

    function captureSelection() {
        const sel = window.getSelection();
        if (!sel || sel.isCollapsed) return;
        const text = sel.toString().trim();
        if (!text) return;
        const range = sel.getRangeAt(0);
        const secId = findSectionFromRange(range.startContainer);
        clearMark();
        try {
            const mark = document.createElement('mark');
            mark.className = 'prose-highlight';
            mark.appendChild(range.extractContents());
            range.insertNode(mark);
            markEl = mark;
            sel.removeAllRanges();
        } catch { /* cross-element selection — no visual mark */ }
        activeHighlight.set(text);
        activeSection.set(secId);
    }

    function findSectionFromEditOffset(offset: number): string {
        // Scan backward in editContent from offset for the last '## Title\n'.
        // Match title → sectionIds[idx].
        const prefix = editContent.slice(0, offset);
        const match = prefix.match(/^## (.+)$/gm);
        if (!match) return '';
        const lastHeader = match[match.length - 1].slice(3).trim();
        const idx = sections.findIndex(s => s.title === lastHeader);
        return idx >= 0 ? (sectionIds[idx] ?? '') : '';
    }

    function captureEditSelection(e: MouseEvent & { currentTarget: HTMLTextAreaElement }) {
        const el = e.currentTarget;
        const sel = el.value.substring(el.selectionStart, el.selectionEnd).trim();
        if (!sel) return;
        activeHighlight.set(sel);
        activeSection.set(findSectionFromEditOffset(el.selectionStart));
    }

    $effect(() => { if (!$activeHighlight) clearMark(); });

    // Section accordion state
    interface Section { title: string; content: string }

    function parseSections(text: string): Section[] {
        const parts = text.split(/^## /m);
        if (parts.length <= 1) return [];
        const sections: Section[] = [];
        for (const part of parts.slice(1)) {
            const newline = part.indexOf('\n');
            if (newline === -1) {
                sections.push({ title: part.trim(), content: '' });
            } else {
                sections.push({
                    title: part.slice(0, newline).trim(),
                    content: part.slice(newline + 1).trim(),
                });
            }
        }
        return sections;
    }

    let sections = $derived((data.sections as Section[]) || parseSections(content));
    let hasSections = $derived(sections.length > 0);

    let outlineMode = $state(false);
    let openSections = $state<Set<number>>(new Set());
    let editSections = $state<Section[]>([]);
    let lastContent = $state('');

    // Re-seed sections when content actually changes
    $effect(() => {
        if (content !== lastContent) {
            editSections = sections.map(s => ({ ...s }));
            openSections = new Set();
            lastContent = content;
        }
    });

    function toggleSection(i: number) {
        const next = new Set(openSections);
        if (next.has(i)) next.delete(i);
        else next.add(i);
        openSections = next;
    }

    function onSectionInput(i: number) {
        dirty = true;
        resetTimer();
    }

    function reconstructContent(): string {
        return editSections.map(s => `## ${s.title}\n\n${s.content}`).join('\n\n');
    }

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
        const finalContent = (hasSections && outlineMode) ? reconstructContent() : editContent;
        if (finalContent !== content) updates.content = finalContent;
        if (Object.keys(updates).length > 0) {
            conversation.updatePost(postId, updates);
        }
        dirty = false;
    }

    function saveAndExit() {
        save();
        if (status !== 'note') editingEnabled = false;
    }

    onDestroy(() => {
        if (dirty && postId) save();
        clearTimer();
    });
</script>

<div class="flex flex-col flex-1 p-6 relative min-h-0">
    <!-- Top-right icon row -->
    <div class="absolute top-4 right-4 flex items-center gap-2 z-10">
        {#if editable}
            <button
                onclick={saveAndExit}
                class="text-[var(--muted)] hover:text-[var(--accent)] cursor-pointer transition-colors"
                title="Save"
            >
                <IconDocumentCheck size={18} />
            </button>
        {:else if status === 'draft'}
            <button
                onclick={enterEditMode}
                class="text-[var(--muted)] hover:text-[var(--accent)] cursor-pointer transition-colors"
                title="Edit"
            >
                <IconPencilSquare size={18} />
            </button>
        {/if}
        {#if editable && hasSections}
            <button
                onclick={() => outlineMode = !outlineMode}
                class="text-[var(--muted)] hover:text-[var(--accent)] cursor-pointer transition-colors"
                title={outlineMode ? 'Expand to full post' : 'Collapse to outline'}
            >
                {#if outlineMode}
                    <IconBarsArrowDown size={18} />
                {:else}
                    <IconBarsArrowUp size={18} />
                {/if}
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

    <!-- Linked post badge -->
    {#if linkedPost}
        <button
            onclick={() => conversation.viewPost(String(linkedPost.post_id))}
            class="flex items-center gap-1 text-xs text-[var(--accent)] hover:underline cursor-pointer mb-2 shrink-0"
        >
            <IconLink size={14} />
            Linked to: {linkedPost.title || linkedPost.post_id}
        </button>
    {/if}

    {#if editable}
        <!-- Edit mode -->
        <input
            type="text"
            bind:value={editTitle}
            oninput={onInput}
            class="text-lg font-semibold bg-transparent text-[var(--secondary)] outline-none border-b border-transparent focus:border-[var(--accent)] transition-colors pr-16 shrink-0"
            placeholder="Title"
        />

        {#if hasSections && outlineMode}
            <!-- Outline view: section accordion -->
            <div class="flex-1 overflow-y-auto mt-2">
                {#each editSections as section, i}
                    <div class="border-b border-[var(--border)]">
                        <button
                            onclick={() => toggleSection(i)}
                            class="flex items-center gap-2 w-full py-2 text-sm font-medium text-[var(--text)] hover:text-[var(--accent)] cursor-pointer transition-colors text-left"
                        >
                            <span class="transition-transform {openSections.has(i) ? 'rotate-90' : ''}">
                                <IconChevronRight size={14} />
                            </span>
                            {section.title}
                        </button>
                        {#if openSections.has(i)}
                            <textarea
                                bind:value={editSections[i].content}
                                oninput={() => onSectionInput(i)}
                                class="block w-full min-h-[40vh] py-2 border-0 bg-transparent text-[var(--text)] text-sm leading-[1.7] resize-y outline-none mb-2"
                                placeholder="Section content..."
                            ></textarea>
                        {/if}
                    </div>
                {/each}
            </div>
        {:else}
            <!-- Standard view: full textarea -->
            <textarea
                bind:value={editContent}
                oninput={onInput}
                onmouseup={captureEditSelection}
                class="flex-1 min-h-0 py-2 border-0 bg-transparent text-[var(--text)] text-sm leading-[1.7] resize-none outline-none w-full"
                placeholder="Start writing..."
                use:focusOnMount={origin === 'create'}
            ></textarea>
        {/if}
    {:else}
        <!-- Non-edit mode: rendered HTML for all post types -->
        {#if title}
            <h3
                ondblclick={enterEditMode}
                class="text-lg font-semibold mb-2 text-[var(--secondary)] pr-16 shrink-0 {status !== 'published' ? 'cursor-text' : ''}"
            >{title}</h3>
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
            <div
                bind:this={proseEl}
                ondblclick={enterEditMode}
                onmouseup={captureSelection}
                class="prose-content text-sm leading-relaxed flex-1 overflow-y-auto {status !== 'published' ? 'cursor-text' : ''}"
            >{@html md(content)}</div>
        {/if}
    {/if}
    {#if pending}
        <div class="text-sm italic text-[var(--muted)] mt-3 shrink-0">
            Outline being generated. Please wait …
        </div>
    {/if}
</div>

<style>
    .prose-content :global(.prose-highlight) {
        background: var(--accent-light);
        border-radius: 3px;
        padding: 0.1em 0.25em;
        margin: 0 -0.05em;
    }
    .prose-content :global(h1) { font-size: 1.5rem; font-weight: 700; margin: 1.25rem 0 0.75rem; }
    .prose-content :global(h2) { font-size: 1.25rem; font-weight: 600; margin: 1rem 0 0.5rem; }
    .prose-content :global(h3) { font-size: 1rem; font-weight: 600; margin: 0.75rem 0 0.4rem; }
    .prose-content :global(p) { margin: 0.5rem 0; }
    .prose-content :global(strong) { font-weight: 600; }
    .prose-content :global(em) { font-style: italic; }
    .prose-content :global(ul), .prose-content :global(ol) { margin: 0.5rem 0; padding-left: 1.5rem; }
    .prose-content :global(ul) { list-style-type: disc; }
    .prose-content :global(ol) { list-style-type: decimal; }
    .prose-content :global(li) { margin: 0.25rem 0; }
    .prose-content :global(ul ul) { list-style-type: circle; margin: 0; }
    .prose-content :global(ul ul li) { margin: 0; }
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
