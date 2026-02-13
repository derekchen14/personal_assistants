<script lang="ts">
  import { displayAlert } from '@alert';
  import { availableSheets, selectSheet, selectedSpreadsheet } from '@store';
  import AlertBox from '../../shared/alertBox.svelte';
  import SelectedIcon from '@lib/icons/Selected.svelte'

  let hoveredSheet = null;
  let hoverRemove = false;
  let hoverSelect = false;

  const removeSheets = (spreadsheet) => {
    availableSheets.update((currentSheets) => currentSheets.filter((item) => item !== spreadsheet));
    displayAlert('warning', `The ${spreadsheet.ssName} data have been removed.`);
  };
</script>

<div class="m-8 p-0 md:p-2 lg:px-4 lg:py-2">
  <AlertBox />

  <p class="font-medium text-xl mb-1">Spreadsheet Manager</p>
  <p class="my-2">
    Each spreadsheet has an associated number of tables. Hover over any of the {$availableSheets.length}
    spreadsheets to see your options. Click on the (-) icon to remove or the (+) icon to select for analysis:
  </p>

  <ul class="mx-8 my-2 list-decimal text-lg">
    {#each $availableSheets as spreadsheet}
    <li class="cursor-pointer"
      on:mouseover={() => hoveredSheet = spreadsheet.ssName}
      on:mouseout={() => hoveredSheet = null}
      on:click={() => selectSheet(spreadsheet)}
      on:focus={() => hoveredSheet = spreadsheet.ssName}
      on:keydown={(e) => { if (e.key === 'Enter') {selectSheet(spreadsheet);} }}
      on:blur={() => hoveredSheet = null}>

      <div class="flex justify-between items-center">
        <div class="flex items-center">  <!-- SPREADSHEET NAME -->
          <span class:text-green-500={spreadsheet.ssName === $selectedSpreadsheet.ssName}
            class="italic transition-all duration-300 ease-in-out
            {hoveredSheet === spreadsheet.ssName ? 'text-teal-500 font-bold' : ''}">
            {spreadsheet.ssName}
          </span>: {spreadsheet.tabNames.join(', ')}

          <div class="px-2 hover:text-teal-500">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5"
              class="w-6 h-6 transition-opacity transition-visibility ease-in-out duration-300
              {hoveredSheet !== spreadsheet.ssName ? 'opacity-0' : 'opacity-100'}"
              stroke="currentColor" on:click={() => selectSheet(spreadsheet)}
              on:keydown={(e) => { if (e.key === 'Enter') { selectSheet(spreadsheet); } }} >
              <path stroke-linecap="round" stroke-linejoin="round"
                d="M12.75 15l3-3m0 0l-3-3m3 3h-7.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
          </div>
        </div>

        {#if spreadsheet.ssName === $selectedSpreadsheet.ssName}
          <div class="text-green-500"><SelectedIcon /></div>
        {/if}
      </div>

    </li>
    {/each}
  </ul>

  <p>
    To return to this view, use the "Help" button in the upper-right, the "Actions" dropdown in the
    bottom panel.  <!-- You can also just ask Dana, "Show me the spreadsheet manager!" -->
  </p>
</div>


<!--  DOCUMENT ICONS
  <div class="flex space-x-2 transition-opacity transition-visibility ease-in-out duration-300
    {hoveredSheet !== spreadsheet.ssName ? 'opacity-0' : 'opacity-100'}">
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" class="w-6 h-6"
    on:mouseover={() => hoverRemove = true}  on:mouseout={() => hoverRemove = false}
    on:focus={() => hoverRemove = true}  on:blur={() => hoverRemove = false}
    on:click={() => removeSheets(spreadsheet)}
    stroke-width={hoverRemove ? "2.1" : "1.5"} stroke={hoverRemove ? "crimson" : "currentColor"}>
      <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m6.75 12H9m1.5-12H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
    </svg>
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" class="w-6 h-6"
    on:mouseover={() => hoverSelect = true}  on:mouseout={() => hoverSelect = false}
    on:focus={() => hoverRemove = true}  on:blur={() => hoverRemove = false}
    on:click={() => selectSheet(spreadsheet)}
    on:keydown={(event) => event.key === 'Enter' ? selectSheet(spreadsheet) : null}
    stroke-width={hoverSelect ? "2.1" : "1.5"} stroke={hoverSelect ? "mediumseagreen" : "currentColor"}>
      <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m3.75 9v6m3-3H9m1.5-12H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
    </svg>
  </div>
-->