<script>
  import { currentFlow } from '@store';
  import PlotFigure from './screens/plotFigure.svelte';
</script>

{#if $currentFlow === 'Visualize(plot)'}
  <PlotFigure />
{:else if $currentFlow === 'Visualize(explain)'}
  <ExplainScreen />
{:else}
  <p>{$currentFlow}</p>
{/if}