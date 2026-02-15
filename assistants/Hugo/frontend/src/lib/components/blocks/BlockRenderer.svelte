<script lang="ts">
    import TableBlock from './TableBlock.svelte';
    import CardBlock from './CardBlock.svelte';
    import ListBlock from './ListBlock.svelte';
    import FormBlock from './FormBlock.svelte';
    import ToastBlock from './ToastBlock.svelte';
    import ConfirmationBlock from './ConfirmationBlock.svelte';

    let { frame }: { frame: { type: string; data: Record<string, unknown>; show: boolean } } = $props();
</script>

{#if frame.type === 'table'}
    <TableBlock data={frame.data} />
{:else if frame.type === 'card'}
    <CardBlock data={frame.data} />
{:else if frame.type === 'list'}
    <ListBlock data={frame.data} />
{:else if frame.type === 'form'}
    <FormBlock data={frame.data} />
{:else if frame.type === 'toast'}
    <ToastBlock data={frame.data} />
{:else if frame.type === 'confirmation'}
    <ConfirmationBlock data={frame.data} />
{:else}
    <div class="text-sm text-[var(--color-text-muted)]">
        Unknown block type: {frame.type}
    </div>
{/if}
