<script>
  import { currentFlow, currentStage } from '@store';
  import PickJustCols from '../stages/pickJustColumns.svelte';
  import CheckboxOpt from '../stages/checkboxOptions.svelte';
</script>

{#if      $currentStage === 'pick-tab-col'}
  <PickJustCols />
{:else if $currentStage === 'checkbox-opt'}
  <CheckboxOpt />
{:else}
  <p>{$currentFlow} error</p>
{/if}