<script lang="ts">
    import { FLOW_MENU } from '$lib/config/flows';
    import { EllipsisVertical, ChevronRight, Trash } from '$lib/components/icons';

    let { onselect, onreset }: { onselect: (dax: string) => void; onreset: () => void } = $props();

    let open = $state(false);
    let activeGroup = $state(-1);
    let menuEl: HTMLElement | undefined = $state();

    function toggle() {
        open = !open;
        if (!open) activeGroup = -1;
    }

    function selectFlow(dax: string) {
        onselect(dax);
        open = false;
        activeGroup = -1;
    }

    function resetChat() {
        onreset();
        open = false;
        activeGroup = -1;
    }
</script>

<svelte:window onclick={(e) => {
    if (open && menuEl && !menuEl.contains(e.target as Node)) {
        open = false;
        activeGroup = -1;
    }
}} />

<div class="relative" bind:this={menuEl}>
    <button onclick={toggle} class="p-1 rounded hover:bg-[var(--color-surface-hover)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors">
        <EllipsisVertical size={20} />
    </button>

    {#if open}
        <div class="absolute right-0 top-full mt-1 w-44 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg shadow-lg z-50 py-1">
            {#each FLOW_MENU as group, i}
                <div
                    class="relative"
                    onmouseenter={() => activeGroup = i}
                >
                    <button class="w-full flex items-center justify-between px-3 py-1.5 text-sm hover:bg-[var(--color-surface-hover)] transition-colors {activeGroup === i ? 'bg-[var(--color-surface-hover)]' : ''}">
                        <span>{group.label}</span>
                        <ChevronRight size={14} class="text-[var(--color-text-muted)]" />
                    </button>

                    {#if activeGroup === i}
                        <div class="absolute left-full top-0 ml-0.5 w-52 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg shadow-lg z-50 py-1 max-h-72 overflow-y-auto">
                            {#each group.flows as flow}
                                <button
                                    onclick={() => selectFlow(flow.dax)}
                                    title={flow.description}
                                    class="w-full text-left px-3 py-1.5 text-sm hover:bg-[var(--color-surface-hover)] transition-colors"
                                >
                                    {flow.name} <span class="text-[var(--color-text-muted)]">{`{${flow.dax}}`}</span>
                                </button>
                            {/each}
                        </div>
                    {/if}
                </div>
            {/each}

            <hr class="my-1 border-[var(--color-border)]" />

            <button onclick={resetChat} class="w-full flex items-center gap-2 px-3 py-1.5 text-sm text-rose-500 hover:text-rose-600 hover:bg-[var(--color-surface-hover)] transition-colors">
                <Trash size={14} />
                <span>Reset Chat</span>
            </button>
        </div>
    {/if}
</div>
