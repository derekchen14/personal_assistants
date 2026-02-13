<script>
  import { createEventDispatcher } from 'svelte';
  export let position = 'left-2 top-2'
  const dispatch = createEventDispatcher();

  function handleClick() {
    dispatch('click', true);
  }
</script>

<svg
  xmlns="http://www.w3.org/2000/svg"
  fill="none"
  viewBox="0 0 24 24" 
  stroke-width="2.5"
  stroke="currentColor" 
  class="w-5 absolute {position}"
  on:click|preventDefault|stopPropagation={handleClick}
  on:keydown={handleClick}>
  <path 
    stroke-linecap="round"
    stroke-linejoin="round" 
    d="m9.75 9.75 4.5 4.5m0-4.5-4.5 4.5M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
</svg>


<style>
  svg { color: white; }
  svg:hover { color: red; }
</style>
