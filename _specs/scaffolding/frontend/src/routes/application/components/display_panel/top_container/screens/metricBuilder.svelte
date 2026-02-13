<script>
  import { currentFlow, currentStage } from '@store';
  import BuildVariables from '../stages/buildVariables.svelte';
  import TimeRange from '../stages/timeRange.svelte';
  import PickTabCols from '../stages/pickTableColumns.svelte';
</script>

{#if      $currentStage === 'build-variables'}
  <BuildVariables />
{:else if $currentStage === 'time-range'}
  <TimeRange />
{:else if $currentStage === 'pick-tab-col'}
  <PickTabCols />
{/if}