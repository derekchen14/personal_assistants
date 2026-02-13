<script>
  export let showStatus;
  export let userId;
  import kalliAvatar from '/src/assets/kalli.png';
  import { agentStatus, chatActive } from '@store';
  import { logger } from '$lib/logger';
  import { onMount } from 'svelte';

  // Track previous active state
  let previouslyActive = false;
  
  // Only log when state changes from active to inactive
  $: {
    const isActive = $agentStatus && $chatActive;
    
    // Log only when transitioning from active to inactive
    if (previouslyActive && !isActive) {
      logger.warning('dana_inactivated', 'ChatWindow', {
        details: {
          agentStatus: $agentStatus,
          chatActive: $chatActive
        }
      });
    }
    
    // Update previous state for next comparison
    previouslyActive = isActive;
  }

  // Initialize previouslyActive on mount
  onMount(() => {
    previouslyActive = $agentStatus && $chatActive;
  });
</script>

<picture class="w-12 relative ml-2 aspect-square">
  {#if userId === 'agent'}
    <img src={kalliAvatar} alt="kalliLogo" class="rounded-2xl" />
  {:else}
    <img src="https://picsum.photos/52" alt="danaLogo" class="rounded-2xl" />
  {/if}

  {#if showStatus}
    {#if $agentStatus && $chatActive}
      <div
        class="w-3 h-3 left-10 top-10 absolute border-slate-200 border-2 rounded-full bg-green-400"
      ></div>
    {:else}
      <div
        class="w-3 h-3 left-10 top-10 absolute border-zinc-300 border-2 rounded-full bg-red-500"
      ></div>
    {/if}
  {/if}
</picture>
