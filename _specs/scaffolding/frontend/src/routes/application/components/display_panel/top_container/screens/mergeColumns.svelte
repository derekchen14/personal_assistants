<script>
  import { currentFlow, currentStage } from '@store';
  import PickJustCols from '../stages/pickJustColumns.svelte';
  import MergeMethod from '../stages/mergeMethod.svelte';
  import CombineCards from '../stages/combineCards.svelte';
  import CombineProgress from '../stages/combineProgress.svelte';
</script>

{#if      $currentStage === 'pick-tab-col'}
  <PickJustCols target='column' />
{:else if $currentStage === 'merge-style'}
  <MergeMethod />
{/if}