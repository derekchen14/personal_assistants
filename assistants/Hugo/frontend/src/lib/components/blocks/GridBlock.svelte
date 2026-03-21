<script lang="ts">
    import { marked } from 'marked';
    import { conversation } from '$lib/stores/conversation';
    import { expandList, bottomFrame } from '$lib/stores/display';
    import IconTrash from '$lib/assets/IconTrash.svelte';
    import IconDocumentCheck from '$lib/assets/IconDocumentCheck.svelte';
    import IconDocumentPlus from '$lib/assets/IconDocumentPlus.svelte';

    let { data }: { data: Record<string, unknown> } = $props();

    function getStatus(item: unknown): string {
        if (typeof item === 'object' && item !== null)
            return ((item as Record<string, unknown>).status as string) || '';
        return '';
    }

    let allItems = $derived((data.items as unknown[]) || []);
    let items = $derived(
        allItems.some(it => getStatus(it) !== '')
            ? allItems.filter(it => getStatus(it) === 'note')
            : allItems
    );

    let confirmDeleteItem: unknown | null = $state(null);
    let creatingNote = $state(false);
    let newNoteBody = $state('');
    let editingId: string | null = $state(null);
    let noteEdits = $state<Record<string, { body: string }>>({});

    let noteCol0 = $derived(items.filter((_, i) => i % 3 === 0));
    let noteCol1 = $derived(items.filter((_, i) => i % 3 === 1));
    let noteCol2 = $derived(items.filter((_, i) => i % 3 === 2));

    function itemId(item: unknown): string | null {
        if (typeof item === 'object' && item !== null)
            return ((item as Record<string, unknown>).post_id as string) || null;
        return null;
    }

    function getContent(item: unknown): string {
        if (typeof item === 'object' && item !== null)
            return ((item as Record<string, unknown>).content as string) || '';
        return '';
    }

    function noteDisplayName(item: unknown): string {
        const first = getContent(item).split('\n')[0] || '';
        return first.replace(/^#+\s*/, '').trim().slice(0, 40) || 'this note';
    }

    function getCharCount(item: unknown): number {
        return getContent(item).length;
    }

    function initNoteEdit(item: unknown) {
        const id = itemId(item);
        if (!id || noteEdits[id]) return;
        noteEdits[id] = { body: getContent(item) };
    }

    function saveNote(id: string) {
        const edits = noteEdits[id];
        if (!edits) return;
        conversation.updateNote(id, edits.body);
    }

    function charCountClass(count: number): string {
        if (count >= 2000) return 'text-red-600';
        if (count >= 1800) return 'text-yellow-600';
        return '';
    }

    function autoresize(el: HTMLTextAreaElement) {
        function resize() {
            el.style.height = 'auto';
            const h = Math.min(el.scrollHeight, 224);
            el.style.height = Math.max(h, 64) + 'px';
            el.style.overflowY = el.scrollHeight > 224 ? 'auto' : 'hidden';
        }
        setTimeout(resize, 0);
        el.addEventListener('input', resize);
        return { destroy() { el.removeEventListener('input', resize); } };
    }

    async function handleNewNoteBlur() {
        const body = newNoteBody.trim();
        if (body.length < 2) { creatingNote = false; newNoteBody = ''; return; }
        conversation.createNote(body);
        creatingNote = false;
        newNoteBody = '';
    }
</script>

<div class="px-2">
    <button
        onclick={expandList}
        class="block w-full text-center text-lg font-semibold underline text-[var(--secondary)] mb-4 cursor-pointer hover:text-[var(--accent)] transition-colors"
    >Your Notes</button>
    <div class="flex gap-3 items-start p-1">
        <div class="flex-1 flex flex-col gap-3">
            {#each noteCol0 as item}
                {@const id = itemId(item)}
                {@const count = id && noteEdits[id] ? noteEdits[id].body.length : getCharCount(item)}
                <div class="group w-full">
                    <div class="note-card">
                        <div class="absolute bottom-4 left-4 flex items-center gap-2">
                            <button
                                class="opacity-0 group-hover:opacity-100 text-[var(--muted)] hover:text-red-500 transition-colors cursor-pointer note-delete-btn"
                                title="Delete"
                                onclick={() => { confirmDeleteItem = item; }}
                            ><IconTrash size={13} /></button>
                            {#if editingId === id}
                                <button
                                    class="text-[var(--muted)] hover:text-[var(--accent)] transition-colors cursor-pointer"
                                    title="Save"
                                    onmousedown={(e) => { e.preventDefault(); saveNote(id!); editingId = null; }}
                                ><IconDocumentCheck size={14} /></button>
                            {/if}
                        </div>
                        {#if editingId === id}
                            <textarea
                                class="min-h-16 overflow-y-hidden w-full bg-transparent border-none outline-none resize-none text-sm leading-relaxed text-[var(--text)] placeholder-[var(--muted)]"
                                placeholder="Write something..."
                                bind:value={noteEdits[id!].body}
                                use:autoresize
                                onblur={() => { saveNote(id!); editingId = null; }}
                            ></textarea>
                        {:else}
                            <div
                                onclick={() => { if (id) { initNoteEdit(item); editingId = id; } }}
                                class="cursor-text note-markdown text-sm min-h-16 max-h-[14em] group-hover:max-h-none overflow-y-auto group-hover:overflow-y-visible w-full text-[var(--text)] transition-[max-height] duration-200"
                                role="textbox"
                                tabindex="0"
                                onkeydown={(e) => { if (e.key === 'Enter' && id) { initNoteEdit(item); editingId = id; } }}
                            >
                                {@html marked.parse(getContent(item))}
                            </div>
                        {/if}
                        <div class="flex justify-end h-5">
                            {#if count > 1000}
                                <span class="text-xs {charCountClass(count)} text-[var(--muted)]">{count}/2000</span>
                            {/if}
                        </div>
                    </div>
                </div>
            {/each}
            {#if items.length % 3 === 0}
                <div class="w-full">
                    {#if creatingNote}
                        <div class="note-card">
                            <textarea
                                class="min-h-16 overflow-y-hidden w-full bg-transparent border-none outline-none resize-none text-sm leading-relaxed text-[var(--text)] placeholder-[var(--muted)] flex-1"
                                placeholder="Write something..."
                                bind:value={newNoteBody}
                                use:autoresize
                                onblur={handleNewNoteBlur}
                                autofocus
                            ></textarea>
                        </div>
                    {:else}
                        <button class="note-card note-card--ghost w-full" onclick={() => { creatingNote = true; }} title="New note">
                            <IconDocumentPlus size={32} />
                        </button>
                    {/if}
                </div>
            {/if}
        </div>
        <div class="flex-1 flex flex-col gap-3">
            {#each noteCol1 as item}
                {@const id = itemId(item)}
                {@const count = id && noteEdits[id] ? noteEdits[id].body.length : getCharCount(item)}
                <div class="group w-full">
                    <div class="note-card">
                        <div class="absolute bottom-4 left-4 flex items-center gap-2">
                            <button
                                class="opacity-0 group-hover:opacity-100 text-[var(--muted)] hover:text-red-500 transition-colors cursor-pointer note-delete-btn"
                                title="Delete"
                                onclick={() => { confirmDeleteItem = item; }}
                            ><IconTrash size={13} /></button>
                            {#if editingId === id}
                                <button
                                    class="text-[var(--muted)] hover:text-[var(--accent)] transition-colors cursor-pointer"
                                    title="Save"
                                    onmousedown={(e) => { e.preventDefault(); saveNote(id!); editingId = null; }}
                                ><IconDocumentCheck size={14} /></button>
                            {/if}
                        </div>
                        {#if editingId === id}
                            <textarea
                                class="min-h-16 overflow-y-hidden w-full bg-transparent border-none outline-none resize-none text-sm leading-relaxed text-[var(--text)] placeholder-[var(--muted)]"
                                placeholder="Write something..."
                                bind:value={noteEdits[id!].body}
                                use:autoresize
                                onblur={() => { saveNote(id!); editingId = null; }}
                            ></textarea>
                        {:else}
                            <div
                                onclick={() => { if (id) { initNoteEdit(item); editingId = id; } }}
                                class="cursor-text note-markdown text-sm min-h-16 max-h-[14em] group-hover:max-h-none overflow-y-auto group-hover:overflow-y-visible w-full text-[var(--text)] transition-[max-height] duration-200"
                                role="textbox"
                                tabindex="0"
                                onkeydown={(e) => { if (e.key === 'Enter' && id) { initNoteEdit(item); editingId = id; } }}
                            >
                                {@html marked.parse(getContent(item))}
                            </div>
                        {/if}
                        <div class="flex justify-end h-5">
                            {#if count > 1000}
                                <span class="text-xs {charCountClass(count)} text-[var(--muted)]">{count}/2000</span>
                            {/if}
                        </div>
                    </div>
                </div>
            {/each}
            {#if items.length % 3 === 1}
                <div class="w-full">
                    {#if creatingNote}
                        <div class="note-card">
                            <textarea
                                class="min-h-16 overflow-y-hidden w-full bg-transparent border-none outline-none resize-none text-sm leading-relaxed text-[var(--text)] placeholder-[var(--muted)] flex-1"
                                placeholder="Write something..."
                                bind:value={newNoteBody}
                                use:autoresize
                                onblur={handleNewNoteBlur}
                                autofocus
                            ></textarea>
                        </div>
                    {:else}
                        <button class="note-card note-card--ghost w-full" onclick={() => { creatingNote = true; }} title="New note">
                            <IconDocumentPlus size={32} />
                        </button>
                    {/if}
                </div>
            {/if}
        </div>
        <div class="flex-1 flex flex-col gap-3">
            {#each noteCol2 as item}
                {@const id = itemId(item)}
                {@const count = id && noteEdits[id] ? noteEdits[id].body.length : getCharCount(item)}
                <div class="group w-full">
                    <div class="note-card">
                        <div class="absolute bottom-4 left-4 flex items-center gap-2">
                            <button
                                class="opacity-0 group-hover:opacity-100 text-[var(--muted)] hover:text-red-500 transition-colors cursor-pointer note-delete-btn"
                                title="Delete"
                                onclick={() => { confirmDeleteItem = item; }}
                            ><IconTrash size={13} /></button>
                            {#if editingId === id}
                                <button
                                    class="text-[var(--muted)] hover:text-[var(--accent)] transition-colors cursor-pointer"
                                    title="Save"
                                    onmousedown={(e) => { e.preventDefault(); saveNote(id!); editingId = null; }}
                                ><IconDocumentCheck size={14} /></button>
                            {/if}
                        </div>
                        {#if editingId === id}
                            <textarea
                                class="min-h-16 overflow-y-hidden w-full bg-transparent border-none outline-none resize-none text-sm leading-relaxed text-[var(--text)] placeholder-[var(--muted)]"
                                placeholder="Write something..."
                                bind:value={noteEdits[id!].body}
                                use:autoresize
                                onblur={() => { saveNote(id!); editingId = null; }}
                            ></textarea>
                        {:else}
                            <div
                                onclick={() => { if (id) { initNoteEdit(item); editingId = id; } }}
                                class="cursor-text note-markdown text-sm min-h-16 max-h-[14em] group-hover:max-h-none overflow-y-auto group-hover:overflow-y-visible w-full text-[var(--text)] transition-[max-height] duration-200"
                                role="textbox"
                                tabindex="0"
                                onkeydown={(e) => { if (e.key === 'Enter' && id) { initNoteEdit(item); editingId = id; } }}
                            >
                                {@html marked.parse(getContent(item))}
                            </div>
                        {/if}
                        <div class="flex justify-end h-5">
                            {#if count > 1000}
                                <span class="text-xs {charCountClass(count)} text-[var(--muted)]">{count}/2000</span>
                            {/if}
                        </div>
                    </div>
                </div>
            {/each}
            {#if items.length % 3 === 2}
                <div class="w-full">
                    {#if creatingNote}
                        <div class="note-card">
                            <textarea
                                class="min-h-16 overflow-y-hidden w-full bg-transparent border-none outline-none resize-none text-sm leading-relaxed text-[var(--text)] placeholder-[var(--muted)] flex-1"
                                placeholder="Write something..."
                                bind:value={newNoteBody}
                                use:autoresize
                                onblur={handleNewNoteBlur}
                                autofocus
                            ></textarea>
                        </div>
                    {:else}
                        <button class="note-card note-card--ghost w-full" onclick={() => { creatingNote = true; }} title="New note">
                            <IconDocumentPlus size={32} />
                        </button>
                    {/if}
                </div>
            {/if}
        </div>
    </div>
</div>

{#if confirmDeleteItem}
    {@const id = itemId(confirmDeleteItem)}
    <div class="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onclick={() => confirmDeleteItem = null} role="presentation">
        <div class="bg-[var(--surface)] border border-[var(--border)] rounded-lg py-5 px-6 max-w-xs w-[90%] shadow-lg" onclick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
            <p class="text-sm font-medium mb-1">Delete "{noteDisplayName(confirmDeleteItem)}"?</p>
            <p class="text-xs text-[var(--muted)] mb-4">This action cannot be undone.</p>
            <div class="flex justify-end gap-2">
                <button
                    class="px-3 py-1.5 text-xs rounded border border-[var(--border)] text-[var(--muted)] hover:text-[var(--text)] cursor-pointer transition-colors"
                    onclick={() => confirmDeleteItem = null}
                >Cancel</button>
                <button
                    class="px-3 py-1.5 text-xs rounded bg-red-500 hover:bg-red-600 text-white font-medium cursor-pointer transition-colors"
                    onclick={() => {
                        if (id) {
                            conversation.deleteNote(id);
                            bottomFrame.set(null);
                        }
                        confirmDeleteItem = null;
                    }}
                >Delete</button>
            </div>
        </div>
    </div>
{/if}
