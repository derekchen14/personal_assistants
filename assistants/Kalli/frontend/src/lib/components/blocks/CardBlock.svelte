<script lang="ts">
    import { md } from '$lib/utils/markdown';
    import { conversation } from '$lib/stores/conversation';

    let { data }: { data: Record<string, unknown> } = $props();

    let title = $derived((data.title as string) || '');
    let content = $derived((data.content as string) || '');
    let fields = $derived((data.fields as Record<string, unknown>) || {});
    let entity = $derived((data.entity as string) || '');

    // Requirement edit state
    let editText = $state('');
    $effect(() => { editText = (data.text as string) || ''; });

    function handleReqBlur() {
        const reqId = data.req_id as string;
        if (reqId && editText.trim()) {
            conversation.updateRequirement(reqId, editText.trim());
        }
    }

    // Tool edit state
    let editName = $state('');
    let editDescription = $state('');
    $effect(() => {
        editName = (data.name as string) || '';
        editDescription = (data.description as string) || '';
    });

    function handleToolBlur() {
        const toolId = data.tool_id as string;
        if (toolId && editName.trim()) {
            conversation.updateTool(toolId, editName.trim(), editDescription.trim());
        }
    }
</script>

<div class="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4 h-full flex flex-col">
    {#if title}
        <h3 class="text-sm font-medium mb-3 text-[var(--color-secondary)]">{title}</h3>
    {/if}

    {#if entity === 'requirement'}
        <textarea
            class="flex-1 resize-none bg-transparent border border-[var(--color-border)] rounded p-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-accent)] placeholder:text-[var(--color-text-muted)]"
            placeholder="Describe a requirement…"
            bind:value={editText}
            onblur={handleReqBlur}
            onkeydown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleReqBlur(); } }}
        ></textarea>
    {:else if entity === 'tool'}
        <div class="flex flex-col gap-3 flex-1">
            <input
                class="text-sm font-medium bg-transparent border-b border-[var(--color-border)] pb-1 outline-none focus:border-[var(--color-accent)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)]"
                placeholder="Tool name"
                bind:value={editName}
                onblur={handleToolBlur}
                onkeydown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleToolBlur(); } }}
            />
            <textarea
                class="flex-1 resize-none bg-transparent border border-[var(--color-border)] rounded p-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-accent)] placeholder:text-[var(--color-text-muted)]"
                placeholder="Description (optional)"
                bind:value={editDescription}
                onblur={handleToolBlur}
            ></textarea>
        </div>
    {:else if Object.keys(fields).length > 0}
        <div class="space-y-2">
            {#each Object.entries(fields) as [key, value]}
                <div class="flex justify-between text-sm">
                    <span class="text-[var(--color-text-muted)]">{key}</span>
                    <span>{String(value)}</span>
                </div>
            {/each}
        </div>
    {:else if content}
        <div class="text-sm leading-relaxed">{@html md(content)}</div>
    {/if}
</div>
