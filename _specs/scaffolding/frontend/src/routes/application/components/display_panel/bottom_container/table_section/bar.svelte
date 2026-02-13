<script>
  // Search Bar and other Actions
  import { Dropdown, DropdownItem, DropdownDivider } from 'flowbite-svelte';
  import { searchQuery, managerView, exportView, displayLayout, saveEdits, saveStatus, showResetModal } from '@store';
  import { onMount } from 'svelte';

  let showActionsDropdown = false;
  let dropdownOpen = false;

  const toggleDisplay = () => {
    displayLayout.set($displayLayout === 'split' ? 'bottom' : 'split');
  };

  const splitDisplay = () => {
    managerView.set(false);
    exportView.set(false);

    displayLayout.set('split');
    dropdownOpen = false;
  };

  const triggerReset = () => {
    dropdownOpen = false;
    showResetModal.set(true);
  };

</script>

<div class="flex flex-col md:flex-row items-center justify-between space-y-3 text-white p-0
  md:space-y-0 md:space-x-4 md:p-1 xl:p-2">

  <div class="w-full md:w-1/2">
    <form class="flex items-center">
      <label for="simple-search" class="sr-only">Search</label>
      <div class="relative w-full">
        <!-- Magnifying Glass -->
        <div class="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
          <svg aria-hidden="true" class="w-5 h-5 text-gray-500 dark:text-gray-400" fill="currentColor"
            viewbox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
            <path d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clip-rule="evenodd" fill-rule="evenodd"/>
          </svg>
        </div>
        <!-- Search Input Box -->
        <input type="text" bind:value={$searchQuery} id="simple-search"
          class="bg-white border shadow-inner border-gray-300 text-slate-800 text-sm rounded-lg focus:ring-primary-500 focus:border-primary-500 block w-full pl-10 p-2 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-primary-500 dark:focus:border-primary-500" placeholder="Search" required=""/>
      </div>
    </form>
  </div>

  {#if $saveStatus === 'active'}
    <span class="text-gray-400 text-sm pt-2 italic">saving ...</span>
  {:else if $saveStatus === 'done'}
    <span class="text-gray-400 text-sm pt-2">Changes saved.</span>
  {:else if $saveStatus === 'error'}
    <span class="text-gray-400 text-sm pt-2">Error saving changes!</span>
  {/if}

  <div class="w-full md:w-auto flex flex-col md:flex-row space-y-2 md:space-y-0 items-stretch md:items-center justify-end md:space-x-3 flex-shrink-0">
    <div class="flex items-center space-x-3 w-full md:w-auto z-20">
      <button on:click={() => (showActionsDropdown = !showActionsDropdown)}
        id="actionsDropdownButton" data-dropdown-toggle="actionsDropdown"
        class="w-full md:w-auto flex items-center justify-right py-2 px-4 text-sm font-medium text-slate-800 focus:outline-none bg-white rounded-lg border border-gray-200 hover:bg-gray-100 hover:text-primary-700 focus:z-10 focus:ring-4 focus:ring-gray-200 dark:focus:ring-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:border-gray-600 dark:hover:text-white dark:hover:bg-gray-700" type="button">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="DarkGoldenRod" class="w-4 h-4 mr-2">
          <path d="M11.983 1.907a.75.75 0 0 0-1.292-.657l-8.5 9.5A.75.75 0 0 0 2.75 12h6.572l-1.305 6.093a.75.75 0 0 0 1.292.657l8.5-9.5A.75.75 0 0 0 17.25 8h-6.572l1.305-6.093Z" />
        </svg>
        Actions
        <svg class="-mr-1 ml-1.5 w-5 h-5" fill="currentColor" viewbox="0 0 20 20" 
          xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <path clip-rule="evenodd" fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"/>
        </svg>
      </button>

      <Dropdown bind:open={dropdownOpen}>
        <DropdownItem on:click={() => {toggleDisplay(); dropdownOpen = false}}>
          <div class="flex items-center">
            {$displayLayout === 'bottom' ? 'Split View' : 'Full View'}
          </div>
        </DropdownItem>
        <DropdownItem on:click={() => {splitDisplay(); $managerView = true;}}>
          Manage Files
        </DropdownItem>
        <DropdownItem on:click={() => {splitDisplay(); $exportView = true;}}>
          Export Data
        </DropdownItem>
        <DropdownItem on:click={saveEdits} disabled={$saveStatus === 'active'}>
          Save Changes
        </DropdownItem>
        <DropdownDivider />
        <DropdownItem on:click={triggerReset}>Reset Chat</DropdownItem>
      </Dropdown>

    </div>
  </div>
</div>
