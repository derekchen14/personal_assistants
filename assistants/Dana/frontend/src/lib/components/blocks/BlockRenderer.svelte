<script lang="ts">
    import TableBlock from './TableBlock.svelte';
    import CardBlock from './CardBlock.svelte';
    import ListBlock from './ListBlock.svelte';
    import FormBlock from './FormBlock.svelte';
    import ToastBlock from './ToastBlock.svelte';
    import ConfirmationBlock from './ConfirmationBlock.svelte';
    import ChartBlock from './ChartBlock.svelte';
    import CompareBlock from './CompareBlock.svelte';

    let { artifact }: { artifact: { type: string; data: Record<string, unknown>; show: boolean } } = $props();
</script>

{#if artifact.type === 'table'}
    <TableBlock data={artifact.data} />
{:else if artifact.type === 'card'}
    <CardBlock data={artifact.data} />
{:else if artifact.type === 'list'}
    <ListBlock data={artifact.data} />
{:else if artifact.type === 'form'}
    <FormBlock data={artifact.data} />
{:else if artifact.type === 'toast'}
    <ToastBlock data={artifact.data} />
{:else if artifact.type === 'confirmation'}
    <ConfirmationBlock data={artifact.data} />
{:else if artifact.type === 'chart'}
    <ChartBlock data={artifact.data} />
{:else if artifact.type === 'compare'}
    <CompareBlock data={artifact.data} />
{:else}
    <div class="text-sm text-[var(--muted)]">
        Unknown block type: {artifact.type}
    </div>
{/if}
