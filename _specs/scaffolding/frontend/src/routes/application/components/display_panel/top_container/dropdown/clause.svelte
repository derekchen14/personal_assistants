<script>
  import { writable } from 'svelte/store';
  import { clickOutside } from './clickOutside.js';
  import { selectedSpreadsheet, selectedTable, tableView, pickedColumns, activatedItem, panelVariables } from '@store';

  import ColorPicker from './colorPicker.svelte';
  import RelationDropdown from './relationPicker.svelte';
  import ColumnDropdown from './columnPicker.svelte';
  import XCircle from '@lib/icons/XCircle.svelte';
  import ChevronDown from '@lib/icons/ChevronDown.svelte';

  export let clause;
  export let varName;
  export let position;
  export let allColors;
  export let rankedTabCols;
  let opened = writable(false);
  let colItems = [];

  $: clauseName = `${varName}_${position}`;       // Unique identifier matching the activatedItem
  $: tabColName = `${clause.tab}.${clause.col}`;  // Unique identifier for the pickedColumns store
  $: label = clause.col ? `${clause.tab === $selectedTable ? '' : clause.tab + '.'}${clause.col}` : '';

  $: if (rankedTabCols.length > 0) {
    // remove columns from rankedTabCols that are already being used
    const existingTabCols = Object.keys($pickedColumns);
    rankedTabCols = rankedTabCols.filter(tc => !existingTabCols.includes(tc.join('.')));
    // set colItems as rankedTabCols followed by all remaining candidate columns in the current table
    colItems = rankedTabCols.map(tc => tc[0] == $selectedTable ? tc[1] : tc.join('.'));
    colItems = colItems.concat(Object.keys($tableView[0]).filter(cand => !colItems.includes(cand)));
  } else {
    colItems = Object.keys($tableView[0])
  }

  function setColumn(event) {
    // Set the current TabCol by parsing the colItem selected by the user
    const tabNames = $selectedSpreadsheet.tabNames;
    const matchingTabName = tabNames.find(tabName => event.detail.colItem.startsWith(`${tabName}.`));
    if (matchingTabName) {  // If colItem starts with a tabName, it's already contains a table and column
      const [tab, col] = event.detail.colItem.split('.');
      clause.tab = tab;
      clause.col = col;
    } else {  // Otherwise use the current table to set the clause attributes
      clause.col = event.detail.colItem;
      clause.tab = $selectedTable;
    }
    let currTabCol = `${clause.tab}.${clause.col}`;

    // Add the newly assigned tabCol item
    if (currTabCol in $pickedColumns) {
      pickedColumns.update(pc => {
        pc[currTabCol]['count'] += 1;
        return pc;
      });
    } else {
      pickedColumns.update(pc => {
        pc[currTabCol] = {color: 'N/A', count: 1};
        return pc;
      })
    }

    panelVariables.update(vars => {
      vars[varName][position] = clause; // Update or add the clause
      return vars;
    });
    activatedItem.set(''); // Reset the activatedItem
    opened.set(false); // Close the dropdown
  }

  function setRelation(event) {
    clause.rel = event.detail.relation; // Update the relation in the clause
    panelVariables.update(vars => {
      vars[varName][position] = clause; // Update the clause within the panelVariables store
      return vars;
    });
  }

  function deleteClause() {
    pickedColumns.update(pc => {
      pc[tabColName]['count'] === 1 ? delete pc[tabColName] : pc[tabColName]['count'] -= 1;
      return pc;
    });
    panelVariables.update(vars => {
      vars[varName].splice(position, 1); // Remove clause at the given position
      return vars;
    });
    activatedItem.set(''); // Reset the activatedItem
  }
</script>

<span class="clause ml-3 text-lg cursor-pointer">
  {#if position !== 0}
    <span on:click={() => $activatedItem = ''}>
      <RelationDropdown initialRelation={clause.rel} on:change={setRelation}/>
    </span>
  {/if}

  <div class="relative inline-block" use:clickOutside={opened}>
    <button on:click={() => opened.update(n => !n)} on:click={() => $activatedItem = `${varName}_${position}`}
      class="glow-border relative dropdown {$opened ? 'dropdown-open' : ''} border border-slate-600
      m-1 pl-7 pr-2 py-0.5 font-medium rounded-md appearance-none font-serif
      {$activatedItem === clauseName ? 'bg-slate-300' : 'bg-white'}">
      {#if position > 0}
        <XCircle on:click={deleteClause} position="left-1.5 top-1.5" />
      {/if}
      <span
        class="inline-block align-middle -mt-1">{label || `(${varName})`}
      </span>
      
      <span class="caret inline-block"><ChevronDown /></span>
    </button>

    {#if $opened}
      <ColumnDropdown {clause} columns={colItems} on:select={setColumn}/>
    {/if}
  </div>

  <ColorPicker {allColors} tabColKey={tabColName} />
</span>

<style>
  .dropdown {
    transition: box-shadow 0.2s ease;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2), 0 1px 2px rgba(0, 0, 0, 0.6);
  }
  .dropdown:hover { /* sky-600 color */
    border-color: rgb(2, 132, 199);
    box-shadow: 0 4px 6px rgba(2, 132, 199, 0.2), 0 1px 2px rgba(2, 132, 199, 0.6);
  }
  .dropdown.dropdown-open {
    border-color: rgb(52, 144, 220);
    border-width: 1px;
    transition: box-shadow 0.2s ease;
    box-shadow: inset 0 1px 3px rgba(0, 0, 0, 1);
  }

  .caret {
    top: 3px;
    position: relative;
    visibility: hidden;
    transform: scaleY(1);
  }

  .dropdown-open .caret {
    visibility: visible;
    transform: scaleY(-1);
  }

  .dropdown:hover .caret {
    visibility: visible;
  }

  .glow-border::before {
    border-width: 2px;
    border-color: rgb(30, 41, 59);
    border-color: transparent;
    border-style: solid;
    content: '';
    position: absolute;
    top: -2px;
    left: -2px;
    right: -2px;
    bottom: -2px;
    border-radius: 8px;
    z-index: 0;
  }

  :global(.dropdown:hover svg) {
    visibility: visible;
  }

</style>