<script>
  import AlertBox from '@shared/alertBox.svelte';
  import ExpandIcon from '@lib/icons/Expand.svelte'
  import CollapseIcon from '@lib/icons/Collapse.svelte'
  import BackIcon from '@lib/icons/Back.svelte'

  import { writable } from 'svelte/store';
  import { createEventDispatcher } from 'svelte';

  // Exported properties so they can be set from outside this component
  export let title = 'Default Title';
  export let subtitle = 'Default Subtitle';

  export let onAccept = (event) => {};
  export let onReject = (event) => {};
  export let acceptLabel = 'OK'
  export let rejectLabel = ''

  export let index = 0;
  export let total = 1;
  export let showToggle = false;
  export let showBack = false;
  export let customClass = 'mb-1';
  export let overflow = false;

  const dispatch = createEventDispatcher();
  let opened = writable(false);

  function toggleEvent() {
    opened.update(n => !n);
    dispatch('toggle', $opened);
  }
  function goBackEvent() {
    dispatch('back', index);
  }

</script>


<div class="mx-6 p-0 md:p-2 lg:px-4 lg:py-6 box-border flex flex-col justify-between h-full">
  <AlertBox />
  <div>
    <h2 class="font-medium text-xl {customClass}">{title}</h2>
    {#if subtitle.length > 0} <p>{subtitle}</p> {/if}
  </div>

  <div class="overflow-visible">
    <div class="flex">
      <slot>No content was provided</slot>
    </div>
  </div>

  <div class="inline-block flex items-center justify-between w-full {overflow ? 'pb-6': ''}">
    {#if showToggle}
      <button on:click={toggleEvent} class="mt-2 mr-3">
        {#if $opened} <CollapseIcon /> {:else} <ExpandIcon /> {/if}
      </button>
    {:else if showBack && index > 0}
      <span class="mt-3 inline-flex">
        <BackIcon customColor="#0c4a6e" customClass="w-4 h-4" />
        <button on:click={goBackEvent} class="text-sm text-sky-900 mx-1.5">Back</button>
      </span>
    {:else}
      <span class="mx-6"></span>
    {/if}

    <div class="flex justify-center items-center gap-4 {$opened ? 'p-4': ''}">
      {#if rejectLabel.length > 0}
        <button class="h-8 px-4 border border-zinc-700 text-sm text-zinc-700 bg-zinc-200 rounded-md cursor-pointer"
        on:click={onReject}>{rejectLabel}</button>
        <button class="h-8 px-4 border border-cyan-700 text-sm text-slate-50 bg-cyan-500 rounded-md cursor-pointer"
        on:click={onAccept}>{acceptLabel}</button>
      {:else}
        <button class="h-8 px-4 mr-8 border border-cyan-700 text-sm text-slate-50 bg-cyan-500 rounded-md cursor-pointer"
        on:click={onAccept}>{acceptLabel}</button>
      {/if}
    </div>

    {#if total > 1}
      <div class="text-sm text-zinc-600 mt-3">
        ({+index + 1} of {total})
      </div>
    {:else}
      <span class="mx-3"></span>
    {/if}
  </div>
</div>