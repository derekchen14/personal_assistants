<script>
  import { currentFlow } from '@store';
  import MetricBuilder from './screens/metricBuilder.svelte';
  import QueryContent from './screens/queryContent.svelte';
</script>

{#if $currentFlow === 'Select(query)'}
  <QueryContent />
{:else if $currentFlow === 'Select(analyze)'}
  <MetricBuilder />
{:else}
  <!-- display the $currentFlow as a paragraph -->
  <p>{$currentFlow}</p>
{/if}