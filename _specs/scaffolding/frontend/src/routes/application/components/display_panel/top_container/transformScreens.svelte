<script>
  import { currentFlow, currentStage } from '@store';
  import MergeColumns from './screens/mergeColumns.svelte';
  import TextToColumns from './screens/textToColumns.svelte';
  import JoinTables from './screens/joinTables.svelte';
  import AppendTable from './screens/appendTable.svelte';
</script>

{#if      $currentFlow === 'Transform(join)'}
  <JoinTables />
{:else if $currentFlow === 'Transform(append)'}
  <AppendTable />
{:else if $currentFlow === 'Transform(merge)'}
  <MergeColumns />
{:else if $currentFlow === 'Transform(split)'}
  <TextToColumns />
{:else}
  <p>{$currentFlow} error</p>
{/if}
