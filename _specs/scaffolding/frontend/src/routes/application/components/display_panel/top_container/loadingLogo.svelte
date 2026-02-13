<script lang="ts">
  import { interactionView, displayLayout, currentFlow, currentStage } from '@store';
  import spinningLogo from '@assets/spinner.gif';
  $: isLearning = $currentStage === 'model-learning';
</script>

<div class="mx-6 p-0 md:p-2 lg:px-4 lg:py-6 box-border flex flex-col justify-between h-full">
  <div>
    <h2 class="font-medium text-xl mb-2">Please Wait</h2>
    {#if isLearning}
      <p class="italic">Learning from your examples ...</p>
    {:else}
      <p class="italic">Thinking hard about the next step ...</p>
    {/if}
  </div>

  <div class="flex-grow flex items-center justify-center">
    <img src={spinningLogo} alt="spinningLogo" class="h-56 xl:h-64" />
  </div>
</div>