<script lang="ts">
    import { fly } from 'svelte/transition';
    import { drawer, dismissDrawer } from '$lib/stores/display';

    let data = $derived(($drawer?.data ?? null) as Record<string, unknown> | null);
    let message = $derived((data?.message as string) || (data?.content as string) || '');
    let level = $derived((data?.level as string) || 'info');

    let accent = $derived(
        level === 'error' ? 'border-red-500' :
        level === 'warning' ? 'border-yellow-500' :
        level === 'success' ? 'border-green-500' :
        'border-[var(--accent)]'
    );
</script>

{#if $drawer && data}
    <div
        class="absolute top-3 left-3 right-3 z-20 rounded-lg border-l-4 {accent} bg-[var(--surface)] shadow-lg px-4 py-3 text-sm flex items-start gap-3"
        transition:fly={{ y: -40, duration: 220 }}
    >
        <p class="flex-1">{message}</p>
        <button
            class="text-[var(--muted)] hover:text-[var(--text)] text-lg leading-none -mt-0.5"
            onclick={dismissDrawer}
            aria-label="Dismiss"
        >×</button>
    </div>
{/if}
