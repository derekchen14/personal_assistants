<script>
  import { currentFlow, currentStage } from '@store';
  import PickTabCols from '../stages/pickTableColumns.svelte';
  import CheckboxOpt from '../stages/checkboxOptions.svelte';
  import CombineCards from '../stages/combineCards.svelte';
  import CombineProgress from '../stages/combineProgress.svelte';
</script>

{#if      $currentStage === 'pick-tab-col'}
  <PickTabCols />
{:else if $currentStage === 'checkbox-opt'}
  <CheckboxOpt />
{:else if $currentStage === 'combine-cards'}          
  <CombineCards />
{:else if $currentStage === 'combine-progress'}
  <CombineProgress target='table' />
{/if}