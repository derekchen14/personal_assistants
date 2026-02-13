<script>
  import { currentFlow, currentStage } from '@store';
  import RemoveDuplicates from './screens/removeDuplicates.svelte';
  import ValidateData from './screens/validateData.svelte';
</script>

{#if $currentFlow === 'Clean(dedupe)'}
  <RemoveDuplicates />
{:else if $currentFlow === 'Clean(validate)'}
  <ValidateData />
{:else}
  <p>{$currentFlow}</p>
{/if}
