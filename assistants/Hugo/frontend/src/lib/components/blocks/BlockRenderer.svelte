<script lang="ts">
    import TableBlock from './TableBlock.svelte';
    import CardBlock from './CardBlock.svelte';
    import ListBlock from './ListBlock.svelte';
    import FormBlock from './FormBlock.svelte';
    import ToastBlock from './ToastBlock.svelte';
    import ConfirmationBlock from './ConfirmationBlock.svelte';
    import CompareBlock from './CompareBlock.svelte';
    import GridBlock from './GridBlock.svelte';

    let { frame }: { frame: { block_type: string; data: Record<string, unknown> } } = $props();
</script>

{#if frame.block_type === 'table'}
    <TableBlock data={frame.data} />
{:else if frame.block_type === 'card'}
    <CardBlock data={frame.data} origin={frame.origin} />
{:else if frame.block_type === 'list'}
    <ListBlock data={frame.data} origin={frame.origin} />
{:else if frame.block_type === 'form'}
    <FormBlock data={frame.data} />
{:else if frame.block_type === 'toast'}
    <ToastBlock data={frame.data} />
{:else if frame.block_type === 'confirmation'}
    <ConfirmationBlock data={frame.data} />
{:else if frame.block_type === 'compare'}
    <CompareBlock data={frame.data} />
{:else if frame.block_type === 'grid'}
    <GridBlock data={frame.data} />
{:else}
    <div class="text-sm text-[var(--muted)]">
        Unknown block type: {frame.block_type}
    </div>
{/if}
