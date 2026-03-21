<script lang="ts">
    /**
     * CardBlock — entity-branched detail / edit panel (bottom panel).
     *
     * The card renders differently based on data.entity:
     *
     *   entity1 (read-only):
     *     Shows a fields dict as key-value rows.  No edit controls.
     *     Example: sheet metadata, channel config.
     *
     *   entity2 (plain-text editable):
     *     A full-height textarea.  Saves on blur (not on a Save button).
     *     Example: SQL query, note body.
     *
     *   entity3 (structured editable):
     *     An inline-editable name input + textarea for the definition.
     *     Both fields saved together on blur of either field.
     *     Example: metric name + SQL definition, requirement name + description.
     *
     *   default:
     *     Falls back to either a fields dict or markdown-rendered content.
     *     Used for agent-generated cards that aren't editable entities.
     *
     * Blur-to-save pattern:
     *   onblur triggers the update call, not a Save button.
     *   This feels native (like a spreadsheet) and avoids extra UI clutter.
     *   Also handle Enter key in single-line inputs for faster keyboard flow.
     *
     * $effect for edit state sync:
     *   When data changes (user selects a different item), $effect re-syncs
     *   editText / editName / editDefinition to the new data values.
     *   Without this, the textarea would keep showing the old item's content.
     *
     * Expand/collapse button:
     *   Shows when the card has content or a known entity type.
     *   Toggles between split (list + card) and bottom (card only, full height).
     *
     * Domain-specific: update the entity branch names and field mappings to
     * match your entity types.
     */

    import { conversation } from '$lib/stores/conversation';
    import { displayLayout, expandPost, collapsePost } from '$lib/stores/display';

    let { data }: { data: Record<string, unknown> } = $props();

    let title  = $derived((data.title   as string) || '');
    let content = $derived((data.content as string) || '');
    let fields  = $derived((data.fields  as Record<string, unknown>) || {});
    let entity  = $derived((data.entity  as string) || '');

    // ── entity2 edit state ────────────────────────────────────────────────────
    let editText = $state('');
    // Sync when data changes (user clicked a different entity2 in the list)
    $effect(() => { editText = (data.text as string) || ''; });

    function handleEntity2Blur() {
        const id = data.entity2_id as string;
        if (id && editText.trim()) {
            conversation.updateEntity2(id, editText.trim());
        }
    }

    // ── entity3 edit state ────────────────────────────────────────────────────
    let editName = $state('');
    let editDefinition = $state('');
    $effect(() => {
        editName = (data.name as string) || '';
        editDefinition = (data.definition as string) || '';
    });

    function handleEntity3Blur() {
        const id = data.entity3_id as string;
        // Only save if the name is non-empty (name is the required field)
        if (id && editName.trim()) {
            conversation.updateEntity3(id, editName.trim(), editDefinition.trim());
        }
    }

    // Show the expand/collapse button whenever there is content to expand
    let showExpandBtn = $derived(!!content || !!entity);
</script>

<div class="p-6 flex-1 relative">

    <!-- Expand / collapse button ─────────────────────────────────────────────
      In 'split' mode: clicking expands the card to full height (hides list).
      In 'bottom' mode: clicking collapses back to split view.
    -->
    {#if showExpandBtn}
        <button
            onclick={() => $displayLayout === 'split' ? expandPost() : collapsePost()}
            class="absolute top-4 right-4 text-[var(--muted)] hover:text-[var(--accent)] cursor-pointer transition-colors text-xs"
            title={$displayLayout === 'split' ? 'Expand' : 'Collapse'}
        >
            {$displayLayout === 'split' ? '⤢' : '⤡'}
        </button>
    {/if}

    {#if entity === 'entity1'}
        <!-- Read-only entity: display fields dict as key-value rows ──────── -->
        {#if title}
            <h3 class="text-lg font-semibold mb-4 text-[var(--secondary)] pr-8">{title}</h3>
        {/if}
        <div class="space-y-2">
            {#each Object.entries(fields) as [key, value]}
                <div class="flex justify-between text-sm">
                    <span class="text-[var(--muted)]">{key}</span>
                    <span>{String(value)}</span>
                </div>
            {/each}
        </div>

    {:else if entity === 'entity2'}
        <!-- Plain-text editable: single textarea, blur-to-save ────────────── -->
        {#if title}
            <h3 class="text-lg font-semibold mb-4 text-[var(--secondary)] pr-8">{title}</h3>
        {/if}
        <textarea
            class="w-full flex-1 resize-none bg-transparent border border-[var(--border)] rounded p-2 text-sm text-[var(--text)] outline-none focus:border-[var(--accent)] placeholder:text-[var(--muted)] font-mono"
            placeholder="Enter text…"
            style="min-height: 8rem;"
            bind:value={editText}
            onblur={handleEntity2Blur}
            onkeydown={(e) => {
                // Save on Enter (without Shift) for single-line-style inputs
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleEntity2Blur();
                }
            }}
        ></textarea>

    {:else if entity === 'entity3'}
        <!-- Structured editable: name input + definition textarea ─────────── -->
        <input
            class="text-lg font-semibold bg-transparent border-b border-[var(--border)] pb-2 outline-none focus:border-[var(--accent)] text-[var(--text)] placeholder:text-[var(--muted)] w-full pr-8 mb-4"
            placeholder="Name"
            bind:value={editName}
            onblur={handleEntity3Blur}
            onkeydown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleEntity3Blur(); } }}
        />
        <textarea
            class="w-full resize-none bg-transparent border border-[var(--border)] rounded p-2 text-sm text-[var(--text)] outline-none focus:border-[var(--accent)] placeholder:text-[var(--muted)]"
            placeholder="Definition (optional)"
            style="min-height: 6rem;"
            bind:value={editDefinition}
            onblur={handleEntity3Blur}
        ></textarea>

    {:else}
        <!-- Default: agent-generated card with fields dict or markdown ──── -->
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
            <!--
                Domain-specific: if you have a markdown utility, use:
                {@html md(content)}
                Otherwise render as pre-formatted text.
            -->
            <div class="text-sm leading-relaxed whitespace-pre-wrap">{content}</div>
        {/if}
    {/if}

</div>
