<script type="ts">
  // Panels take care of layout, while the Containers handle the content
  import TopContainer from './top_container/topContainer.svelte';
  import BottomContainer from './bottom_container/bottomContainer.svelte';
  import { displayLayout } from '@store'; // choose from [default, top, bottom]
</script>

<div class="flex grow-[3] md:grow-1 flex-col w-full max-w-full gap-y-2 text-slate-800">
  <!-- for the child containers-->

  {#if $displayLayout === 'top' || $displayLayout === 'split'}
    <div class={`top-container grow-[2] h-0 shadow-md`}>
      <TopContainer />
    </div>
  {/if}

  {#if $displayLayout === 'bottom' || $displayLayout === 'split'}
  <div class={`bottom-container shadow-md
    grid grid-cols-1 grid-rows-1 grow-[2]
    h-0 w-full min-w-0`}>
    <BottomContainer />
  </div>
  {/if}

</div>
