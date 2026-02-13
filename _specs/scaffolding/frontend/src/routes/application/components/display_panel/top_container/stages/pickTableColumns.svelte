<script lang="ts">
  import { writable, get } from 'svelte/store';
  import { serverUrl, receiveData, interactionView, selectedSpreadsheet, selectTab, messageStore } from '@store';
  import { resetInteractions, pickedColumns, activatedItem, tableView, panelVariables, currentFlow } from '@store';
  import { displayAlert } from '@alert';
  import { securedFetch } from '$lib/apiUtils';

  import AddIcon from '@lib/icons/Add.svelte'
  import Constraint from '../dropdown/tableConstraint.svelte';
  import InteractivePanel from './components/interactiveComp.svelte';

  let stage = '';
  let tabNames = [];
  let tabColorMap = {'left': 'sky', 'right': 'emerald'};
  let pickedTabs = {'left': '', 'right': ''};

  $: tabNames = $selectedSpreadsheet.tabNames;

  $: if ($interactionView.content && $resetInteractions) {
    const { flowType, content } = $interactionView;
    const selected = content['selected'];

    let activeTab = selected[0].tab;
    selectTab(activeTab);

    ['left', 'right'].forEach(side => {
      // Unpack the tabColItems from the selected array
      $panelVariables[side] = selected.filter(item => item.side === side);
      // Parse the tabColItem to initialize the pickedColumns and pickedTabs
      $panelVariables[side].forEach(({ tab, col, side }) => {
        pickedColumns.update(pc => {
          pc[`${tab}.${col}`] = { color: tabColorMap[side], count: 1 };
          return pc;
        });
        pickedTabs[side] = tab;
      });
    });
    $currentFlow = flowType;
    $resetInteractions = false;
  }

  // If pickedColumns has changed, then check for 'N/A' colors and fill them
  $: if ($pickedColumns) {
    const pickedCols = get(pickedColumns);
    Object.entries(pickedCols).forEach(([tabColName, { color }]) => {
      if (color === 'N/A') {
        pickedColumns.update(pc => {
          const pcTable = tabColName.split('.')[0];
          const side = pcTable === pickedTabs['left'] ? 'left' : 'right';
          pc[tabColName].color = tabColorMap[side];
          return pc;
        });
      }
    });
  }

  function addUserUtterance() {
    let columnNames = {'left': [], 'right': []};
    let tabNames = {'left': '', 'right': ''};
    $panelVariables['left'].forEach(item => {
      columnNames['left'].push(item['col']);
      tabNames['left'] = item['tab'];
    })
    $panelVariables['right'].forEach(item => {
      columnNames['right'].push(item['col']);
      tabNames['right'] = item['tab'];
    })
    const leftString = columnNames['left'].join(', ') + ' columns in ' + tabNames['left'];
    const rightString = columnNames['right'].join(', ') + ' columns in ' + tabNames['right'];
    let message = `Please merge the tables based on the ${leftString} and the ${rightString}.`;

    messageStore.set({
      message: { type: 'text', content: message },
      userId: 'user', time: new Date()
    });
  }


  function pickNewTable(side, event) {
    const previousTab = pickedTabs[side];
    const currentTab = event.target.value;

    pickedTabs[side] = currentTab;
    selectTab(currentTab);
    activatedItem.set(`${side}_0`);

    pickedColumns.update(pc => {
      Object.keys(pc).forEach(tabCol => {
        if (tabCol.startsWith(previousTab)) { delete pc[tabCol]; }
      });
      pc[`${currentTab}.`] = { color: tabColorMap[side], count: 1 };
      return pc;
    });

    panelVariables.update(vars => {
      vars[side] = [{ tab: event.target.value, col: '', side }];
      return vars;
    });
  }

  function createConstraint(table, column, side) {
    let constraint = { tab: table, col: column, side };
    let tabColName = `${table}.${column}`;

    $activatedItem = `${side}_${$panelVariables[side].length}`;
    panelVariables.update(vars => {
      vars[side].push(constraint);
      return vars;
    });

    pickedColumns.update(pc => {
      pc[tabColName] = { color: tabColorMap[side], count: 1 };
      return pc;
    });
  }

  const handleCancel = () => {
    const payload = { flowType: 'Transform(join)', stage: 'cancel', selected: [] };
    currentFlow.set(null);
    pickedColumns.set({});

    securedFetch(`${serverUrl}/interactions/merge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(res => res.json())
      .then(data => {receiveData(data)})
      .catch(err => console.log(err));
  }

  function handleFinish() {
    const payload = { flowType: 'Transform(join)', stage: 'pick-tab-col', selected: [] };
    currentFlow.set(null);
    pickedColumns.set({});
    let emptySide = '';  // Track if there are valid columns for both tables

    for (const side of ['left', 'right']) {
      const filteredItems = $panelVariables[side].filter(item => item.tab && item.col);

      if (filteredItems.length === 0) {
        emptySide += emptySide.length > 0 ? ` and ${side}` : side; // Append a side flag if no valid items found
      } else {
        const tabColItems = filteredItems.map(item => ({ ...item, ver: true, side: side }));
        payload.selected = [...payload.selected, ...tabColItems];
      }
    }
    if (emptySide.length > 0) {
      displayAlert('warning', `Please select at least one column for the ${emptySide} table`);
      return; // Prevent further execution if no valid items are found
    }

    addUserUtterance();
    securedFetch(`${serverUrl}/interactions/merge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(res => res.json())
      .then(data => {receiveData(data)})
      .catch(err => console.log(err));
  }
</script>

<InteractivePanel
  title="Connect Two Tables with Fuzzy Join" subtitle="Please choose the tables to connect. I will then compare the selected columns to see if they are similar. When they match, the entries will be merged together. Otherwise, they will stay as two separate rows."
  onReject={handleCancel} rejectLabel="Cancel"
  onAccept={handleFinish} acceptLabel="Next"
  index=0 total=3>

  <!-- Loop through left and right table picking -->
  {#each Object.entries(pickedTabs) as [side, pickedTabName]}

    <div class="flex flex-col mx-auto group {$panelVariables[side].length < 3 ? 'mt-4' : ''}">
      <select value={pickedTabName} on:change={(event) => pickNewTable(side, event)}
        class="w-full py-1.5 pl-3 border border-zinc-400 rounded font-serif">
        {#each tabNames as table}
          <option disabled={Object.values(pickedTabs).includes(table)}
          value={table}>{table}</option>
        {/each}
      </select>

      {#each $panelVariables[side] as constraint, pos}
        <div class="flex ml-2 mr-5">
          <svg fill="none" viewBox="0 0 50 30" stroke-width="4" stroke="SlateGray" class="w-10 h-10">
            <path d="M10 0 L10 30 L50 30" />
          </svg>
          <Constraint {constraint} {side} minSize=1 position={pos}/>
        </div>
      {/each}

      {#if $panelVariables[side].length < 3}
        <button on:click={() => createConstraint(pickedTabName, '', side)} class="mx-auto mt-4 p-1 pr-2 w-20 h-9
          rounded bg-green-700/10 text-green-600 border-2 border-green-600 cursor-pointer 
          transition-opacity duration-200 group-hover:opacity-100 opacity-0">
          <AddIcon/> Add
        </button>
      {/if}
    </div>

  {/each}
</InteractivePanel>