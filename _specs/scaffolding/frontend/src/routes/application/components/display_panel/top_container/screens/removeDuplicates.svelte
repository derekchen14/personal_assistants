<script>
  import { currentFlow, currentStage } from '@store';
  import PickJustCols from '../stages/pickJustColumns.svelte';
  import MergeStyle from '../stages/mergeStyle.svelte';
  import CombineRows from '../stages/combineRows.svelte';
  import CombineProgress from '../stages/combineProgress.svelte';
</script>

{#if      $currentStage === 'pick-tab-col'}
  <PickJustCols target='row' />
{:else if $currentStage === 'merge-style'}
  <MergeStyle target='row' />
{:else if $currentStage === 'combine-cards'}          
  <CombineRows />
{:else if $currentStage === 'combine-progress'}
  <CombineProgress />
{/if}