<script>
  export let title;
  export let items = [];
  export let onSelect;
  export let onDelete;
  export let loading = false;

  let hoveredItem = null;
  function getDisplayName(item) {
    return item.ssName || item.name || '';
  }
</script>

<div class="mt-6">
  <p class="mb-2">{title}</p>
  {#if loading}
    <div class="animate-pulse">
      <div class="h-4 bg-gray-200 rounded w-3/4 mb-4"></div>
      <div class="h-4 bg-gray-200 rounded w-1/2"></div>
    </div>
  {:else if items.length > 0}
    <ol class="mx-8 my-1 list-disc text-lg">
      {#each items as item}
        <li class="cursor-pointer"
          on:mouseover={() => (hoveredItem = getDisplayName(item))}
          on:mouseout={() => (hoveredItem = null)}
          on:click={() => onSelect(item)}
          on:focus={() => (hoveredItem = getDisplayName(item))}
          on:keydown={(e) => { if (e.key === 'Enter') {onSelect(item);} }}
          on:blur={() => (hoveredItem = null)}>

          <div class="flex items-center">
            <span class="italic transition-all duration-300 ease-in-out
              {hoveredItem === getDisplayName(item) ? 'text-teal-500 font-bold' : ''}">
              {getDisplayName(item)}
            </span>: {item.data_sources?.join(', ') || item.tabNames?.join(', ')}

            <div class="px-2 hover:text-teal-500">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5"
                class="w-6 h-6 transition-opacity transition-visibility ease-in-out duration-300
                {hoveredItem !== getDisplayName(item) ? 'opacity-0' : 'opacity-100'}"
                stroke="currentColor" on:click={() => onSelect(item)}>
                <path stroke-linecap="round" stroke-linejoin="round"
                  d="M12.75 15l3-3m0 0l-3-3m3 3h-7.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </div>

            {#if onDelete}
              <div class="px-2 hover:text-red-500">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5"
                  class="w-6 h-6 transition-opacity transition-visibility ease-in-out duration-300
                  {hoveredItem !== getDisplayName(item) ? 'opacity-0' : 'opacity-100'}"
                  stroke="currentColor" on:click={(e) => onDelete(item.id, e)}>
                  <path stroke-linecap="round" stroke-linejoin="round"
                    d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"/>
                </svg>
              </div>
            {/if}
          </div>

        </li>
      {/each}
    </ol>
  {:else}
    <p class="text-gray-500 italic">No items available</p>
  {/if}
</div>