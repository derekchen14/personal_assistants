<script lang="ts">
    import { FLOW_MENU } from '$lib/config/flows';
    import { theme, toggleTheme } from '$lib/stores/display';
    import IconChevronDown from '$lib/assets/IconChevronDown.svelte';
    import IconTrash from '$lib/assets/IconTrash.svelte';
    import IconSun from '$lib/assets/IconSun.svelte';
    import IconMoon from '$lib/assets/IconMoon.svelte';

    let { onselect, onreset, open = $bindable(false) }: {
        onselect: (dax: string) => void;
        onreset: () => void;
        open?: boolean;
    } = $props();

    let expandedGroup = $state(-1);

    function toggleGroup(i: number) {
        expandedGroup = expandedGroup === i ? -1 : i;
    }

    function selectFlow(dax: string) {
        onselect(dax);
        open = false;
        expandedGroup = -1;
    }

    function resetChat() {
        onreset();
        open = false;
        expandedGroup = -1;
    }
</script>

{#if open}
    <!-- Sidebar overlay -->
    <div
        class="fixed inset-0 z-40"
        onclick={() => { open = false; expandedGroup = -1; }}
        role="presentation"
    ></div>

    <!-- Sidebar panel -->
    <div class="absolute left-0 top-full mt-0 w-64 bg-[var(--surface)] border border-[var(--border)] rounded-b-lg shadow-lg z-50 max-h-[calc(100vh-4rem)] overflow-y-auto">
        <div class="py-2">
            {#each FLOW_MENU as group, i}
                <div>
                    <button
                        onclick={() => toggleGroup(i)}
                        class="w-full flex items-center justify-between px-4 py-2 text-sm font-medium hover:bg-[var(--hover)] transition-colors"
                    >
                        <span>{group.label}</span>
                        <span class="transition-transform duration-200 {expandedGroup === i ? 'rotate-180' : ''}">
                            <IconChevronDown size={16} class="text-[var(--muted)]" />
                        </span>
                    </button>

                    {#if expandedGroup === i}
                        <div class="pb-1">
                            {#each group.flows as flow}
                                <button
                                    onclick={() => selectFlow(flow.dax)}
                                    title={flow.description}
                                    class="w-full text-left px-8 py-1.5 text-sm hover:bg-[var(--hover)] transition-colors text-[var(--muted)]"
                                >
                                    {flow.name} <span class="opacity-60">{`{${flow.dax}}`}</span>
                                </button>
                            {/each}
                        </div>
                    {/if}
                </div>
            {/each}

            <hr class="my-1 border-[var(--border)]" />

            <button
                onclick={toggleTheme}
                class="w-full flex items-center gap-2 px-4 py-2 text-sm text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--hover)] transition-colors"
            >
                {#if $theme === 'light'}
                    <IconMoon size={14} />
                    <span>Dark Mode</span>
                {:else}
                    <IconSun size={14} />
                    <span>Light Mode</span>
                {/if}
            </button>

            <button
                onclick={resetChat}
                class="w-full flex items-center gap-2 px-4 py-2 text-sm text-rose-500 hover:text-rose-600 hover:bg-[var(--hover)] transition-colors"
            >
                <IconTrash size={14} />
                <span>Reset Chat</span>
            </button>
        </div>
    </div>
{/if}
