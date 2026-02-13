<script>
  import { createEventDispatcher } from 'svelte';
  
  export let title;
  export let showRefresh = true;
  let showDropdown = false;
  let menuButton;
  const dispatch = createEventDispatcher();

  function handleClickOutside(event) {
    if (menuButton && !menuButton.contains(event.target)) {
      showDropdown = false;
    }
  }
</script>

<svelte:window on:click={handleClickOutside} />

<div class="flex justify-between items-center border-b py-3 px-4">
  <div class="flex items-center gap-2">
    <h3 class="text-lg font-semibold">{title}</h3>
    <div class="relative">
      <button
        bind:this={menuButton}
        class="p-1 hover:bg-gray-100 rounded-full"
        on:click|stopPropagation={() => showDropdown = !showDropdown}
      >
        <svg class="w-5 h-5 text-gray-600" viewBox="0 0 24 24" fill="currentColor">
          <path d="M6 10c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm12 0c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm-6 0c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z" />
        </svg>
      </button>
      
      {#if showDropdown}
        <div class="absolute left-0 mt-1 py-1 w-48 bg-white rounded-md shadow-lg border z-20">
          {#if showRefresh}
            <button
              class="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 border-b"
              on:click={() => {
                dispatch('refresh');
                showDropdown = false;
              }}
            >
              Refresh List
            </button>
          {/if}
          <button
            class="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-gray-100"
            on:click={() => dispatch('disconnect')}
          >
            Disconnect
          </button>
        </div>
      {/if}
    </div>
  </div>
  <slot />
</div>
