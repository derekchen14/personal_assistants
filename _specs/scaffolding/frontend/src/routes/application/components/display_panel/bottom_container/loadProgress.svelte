<script lang="ts">
  import { selectedSpreadsheet, chatActive } from '@store';
  import { Progressbar } from 'flowbite-svelte';
  import { onMount, onDestroy } from 'svelte';

  let progress = 0;
  let interval;

  onMount(() => {
    let avgTimePerColumn = 1000;

    interval = setInterval(() => {
      const increments = [5, 10, 15];
      const randomIncrement = increments[Math.floor(Math.random() * 3)];
      progress = Math.min(progress + randomIncrement, 100);
    }, avgTimePerColumn); // This function will be called every few seconds
  });

  onDestroy(() => {
    clearInterval(interval);
  });
</script>

<div class="flex p-8 items-center justify-center">
  <div class="m-3 pt-8 w-5/6">
    <div class="mx-4 mb-8 text-lg font-medium dark:text-white">Loading ...</div>
    {#if $chatActive}
      <Progressbar progress="100" color="blue" size="h-5" />
    {:else}
      <Progressbar animate {progress} color="blue" size="h-5" />
    {/if}
  </div>
</div>
