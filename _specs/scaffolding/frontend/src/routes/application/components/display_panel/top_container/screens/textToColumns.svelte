<script>
  import { currentFlow, currentStage } from '@store';
  import PickJustCols from '../stages/pickJustColumns.svelte';
  import SplitStyle from '../stages/splitStyle.svelte';
</script>

{#if      $currentStage === 'pick-tab-col'}
  <PickJustCols target='column' />
{:else if $currentStage === 'split-style'}
  <MergeStyle target='column' />
{/if}