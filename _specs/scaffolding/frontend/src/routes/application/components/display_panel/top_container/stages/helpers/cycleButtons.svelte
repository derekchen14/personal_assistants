<script>
  import CycleUpIcon from '@lib/icons/CycleUp.svelte'
  import CycleDownIcon from '@lib/icons/CycleDown.svelte'
  import { createEventDispatcher } from 'svelte';

  export let side;
  export let numCards;
  export let chosenCards;

  const dispatch = createEventDispatcher();
  function triggerCycleCard(direction) {
    dispatch('cycle', { side:side , direction:direction });
  }
</script>

<div class="flex flex-col items-center group">
  
  <!-- Card Index -->
  <div class="{numCards[side] > 1 ? 'text-slate-600':'text-slate-300'} mt-1 mb-2 invisible group-hover:visible">
    {chosenCards[side] + 1} / {numCards[side]}
  </div>

  <!-- Up Button -->
  <button class="p-1.5 xl:p-2" on:click={() => triggerCycleCard('up')}>
    <CycleUpIcon active={numCards[side] > 1}/>
  </button>

  <!-- Down Button -->
  <button class="p-1.5 xl:p-2" on:click={() => triggerCycleCard('down')}>
    <CycleDownIcon active={numCards[side] > 1}/>
  </button>

</div>