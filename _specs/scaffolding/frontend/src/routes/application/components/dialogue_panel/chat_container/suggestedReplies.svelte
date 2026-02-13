<script>
  import { fade } from 'svelte/transition';
  import { sendMessage, flowDax, userActions, hasSuggestion, replyPillData } from '@store';

  let hoveredPillIndex = null;

  function chooseSuggestion(replyPill, index) {
    flowDax.set(replyPill.dax);
    let action = { type: 'REPLY', payload: replyPill.action };
    userActions.set(action);
    sendMessage(replyPill.text);
  }
</script>

{#if $hasSuggestion}
<div class="flex flex-wrap justify-center space-x-2 mt-3">

  {#each $replyPillData as replyPill, pillIndex}
    <div class="relative">
      <button class="px-4 py-2 m-1 bg-indigo-50 text-cyan-800 text-sm rounded-full border border-cyan-900
        hover:bg-cyan-200 transition-colors duration-200 ease-in-out"
        on:click={() => chooseSuggestion(replyPill, pillIndex)}
        on:mouseenter={() => hoveredPillIndex = pillIndex}
        on:mouseleave={() => hoveredPillIndex = null}>
        {replyPill.text}
      </button>

      {#if hoveredPillIndex === pillIndex}
        <div transition:fade="{{ duration: 100 }}"
          class="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-2 py-1
               bg-gray-800 text-white text-xs rounded shadow-lg z-20">
          Key-{pillIndex + 1}
        </div>
      {/if}
    </div>
  {/each}

</div>
{/if}