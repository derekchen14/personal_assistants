<script>
  import { tableType } from '@store';
  import ActionBar from './bar.svelte';
  import DirectTable from './direct.svelte';
  import DerivedTable from './derived.svelte';
  import DynamicTable from './dynamic.svelte';
  import DecisionTable from './decision.svelte';
</script>

<div id="full-table" class="mx-3 py-2 justify-center">

  {#if $tableType == 'direct'}
    <ActionBar />
    <DirectTable />
  {:else if $tableType == 'derived'}
    <DerivedTable />
  {:else if $tableType == 'dynamic'}
    <DynamicTable />
  {:else if $tableType == 'decision'}
    <DecisionTable />
  {/if}
</div>

<style>
  #full-table {
    height: calc(100% - 1rem);
  }
</style>
