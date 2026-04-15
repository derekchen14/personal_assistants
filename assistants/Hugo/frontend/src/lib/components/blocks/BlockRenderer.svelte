<script lang="ts">
    import TableBlock from './TableBlock.svelte';
    import CardBlock from './CardBlock.svelte';
    import ListBlock from './ListBlock.svelte';
    import FormBlock from './FormBlock.svelte';
    import ToastBlock from './ToastBlock.svelte';
    import ConfirmationBlock from './ConfirmationBlock.svelte';
    import CompareBlock from './CompareBlock.svelte';
    import GridBlock from './GridBlock.svelte';
    import SelectionBlock from './SelectionBlock.svelte';
    import type { Block, FrameData } from '$lib/stores/display';

    let { frame, location = 'bottom' }:
        { frame: FrameData; location?: 'top' | 'bottom' } = $props();

    // Accept both the new blocks-array shape and the legacy single-block shape.
    let renderable = $derived.by(() => {
        if (frame?.blocks && frame.blocks.length > 0) {
            return frame.blocks.filter(b => (b.location ?? 'bottom') === location);
        }
        if (frame?.block_type) {
            return [{ type: frame.block_type, data: frame.data ?? {}, location }] as Block[];
        }
        return [] as Block[];
    });
</script>

{#each renderable as block}
    {#if block.type === 'table'}
        <TableBlock data={block.data} />
    {:else if block.type === 'card'}
        <CardBlock data={block.data} origin={frame.origin ?? ''} />
    {:else if block.type === 'list'}
        <ListBlock data={block.data} origin={frame.origin ?? ''} />
    {:else if block.type === 'form'}
        <FormBlock data={block.data} />
    {:else if block.type === 'toast'}
        <ToastBlock data={block.data} />
    {:else if block.type === 'confirmation'}
        <ConfirmationBlock data={block.data} />
    {:else if block.type === 'compare'}
        <CompareBlock data={block.data} />
    {:else if block.type === 'grid'}
        <GridBlock data={block.data} />
    {:else if block.type === 'selection'}
        <SelectionBlock data={block.data} origin={frame.origin ?? ''} />
    {:else if block.type !== 'default'}
        <div class="text-sm text-[var(--muted)]">Unknown block type: {block.type}</div>
    {/if}
{/each}
