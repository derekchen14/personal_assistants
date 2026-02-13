<script>
  import { writable } from 'svelte/store';
  import { clickOutside } from './clickOutside.js';
  import { selectedTable, tableView, pickedColumns, activatedItem, panelVariables } from '@store';
  import { displayAlert } from '@alert';

  import ColumnDropdown from './columnPicker.svelte';
  import XCircle from '@lib/icons/XCircle.svelte';
  import ChevronDown from '@lib/icons/ChevronDown.svelte';

  export let constraint;
  export let position;
  export let minSize;

  let opened = writable(false);
  let colMenuItems = [];

  $: constraintName = `items_${position}`;             // Unique identifier matching the activatedItem
  $: colMenuItems = Object.keys($tableView[0])

  function setColumn(colItem) {
    // Prevent user from selecting columns from different tables
    const existingTables = Object.keys($pickedColumns).map(tabCol => tabCol.split('.')[0]);
    if (existingTables.length > 0 && !existingTables.includes($selectedTable)) {
      let warningMessage = 'Selected columns must come from the same table. Please remove other columns first before proceeding.';
      displayAlert('warning', warningMessage);
      return;
    }

    let prevTabCol = `${constraint.tab}.${constraint.col}`;
    let currTabCol = `${$selectedTable}.${colItem}`;

    if (currTabCol === prevTabCol) {
      // If you select the same column, then it becomes de-selected
      pickedColumns.update(pc => {
        delete pc[prevTabCol];
        return pc;
      });
      constraint.col = '';
    } else {
      // If you choose something that is already picked, throw a warning
      if (currTabCol in $pickedColumns) {
        displayAlert('warning', `The ${currTabCol} column has already been selected.`);
        return;
      // Otherwise, successfully add the new column to pickedColumns
      } else {
        pickedColumns.update(pc => {
          delete pc[prevTabCol];
          pc[currTabCol] = {color: 'sky', count: 1};
          return pc;
        })
        constraint.tab = $selectedTable;
        constraint.col = colItem;
        constraint.ver = true;
      }
    }

    panelVariables.update(vars => {
      vars['items'][position] = constraint; // Update or add the constraint
      return vars;
    });

    activatedItem.set(''); // Reset the activatedItem
    opened.set(false); // Close the dropdown
  }

  function deleteConstraint() {
    let tabColName = `${constraint.tab}.${constraint.col}`;   // Unique identifier for the pickedColumns store

    pickedColumns.update(pc => {
      pc[tabColName]['count'] === 1 ? delete pc[tabColName] : pc[tabColName]['count'] -= 1;
      return pc;
    });
    panelVariables.update(vars => {
      // Remove constraint at the given position
      vars['items'].splice(position, 1);
      // If there are no more constraints, add a default one
      if (vars['items'].length === 0) {
        vars['items'] = [{ tab: $selectedTable, col: '', ver: true }];
      }
      return vars;
    });

    activatedItem.set('');
  }
</script>

<span class="constraint mx-3 text-lg cursor-pointer">
  <div class="relative inline-block" use:clickOutside={opened}>
    <button on:click={() => opened.update(n => !n)} on:click={() => $activatedItem = `items_${position}`}
      class="glow-border relative dropdown {$opened ? 'dropdown-open' : ''} border border-slate-600
      m-1 pl-7 pr-2 py-1 font-medium rounded-md appearance-none font-serif
      {$activatedItem === constraintName ? 'bg-slate-300' : 'bg-white'}">
      {#if Object.keys($pickedColumns).length > minSize}
        <XCircle on:click={deleteConstraint} position="left-1.5 top-2"/>
      {/if}

      {#if constraint.col}
        <span class="inline-block align-middle -mt-1">{constraint.col}</span>
      {:else}
        <span class="inline-block align-middle -mt-1 text-base italic">(none)</span>
      {/if}
      <span class="caret inline-block"><ChevronDown /></span>
    </button>

    {#if $opened}
      <div class="min-w-full z-20 absolute bg-white divide-y divide-gray-100 rounded-md shadow">
        <ul class="py-2 text-sm text-gray-700 dark:text-gray-200">
          {#each colMenuItems as colItem}
          <li on:click|stopPropagation={() => setColumn(colItem)}>
            <span class="whitespace-nowrap block px-4 py-1 hover:bg-cyan-100"> {colItem} </span>
          </li>
          {/each}
        </ul>
      </div>
    {/if}

  </div>
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