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
    import type { FrameData } from '$lib/stores/display';

    let { frame, location = 'bottom' }:
        { frame: FrameData; location?: 'top' | 'bottom' } = $props();

    let renderable = $derived(
        (frame?.blocks ?? []).filter(b => (b.location ?? 'bottom') === location),
    );
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
