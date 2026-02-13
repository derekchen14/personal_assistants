<script>
  import { currentStage, currentFlow } from '@store';
  import ModifyQuery from '../stages/modifyQuery.svelte';
  import ThoughtProcess from '../stages/thoughtProcess.svelte';
  import DefaultContent from '../stages/defaultContent.svelte';
</script>

{#if      $currentFlow === 'Select(query)'}
  <ModifyQuery />
{:else if $currentFlow === 'Default(thought)'}
  <ThoughtProcess />
{:else}
  <DefaultContent />
{/if}