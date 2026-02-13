<script>
  import { tableView, pickedColumns, activatedItem, panelVariables } from '@store';
  import { selectedTable, fetchData, sheetData, tabSwitchTrigger, currentFlow } from '@store'; // from dataStore
  import { onDestroy, onMount } from 'svelte';
  import { fade } from 'svelte/transition';
  import { displayAlert } from '@alert';

  let tableRegion;
  let columnNames = [];
  let columnWidths = {};
  let dataToDisplay = [];
  let cellColors = {};

  let isDataEnd = false;
  let unsubscribe;

  // Table with limited viewing functionality, but allows for column picking in collaboration with interactive panel
  onMount(() => { unsubscribe = tableView.subscribe(displayData); });
  onDestroy(() => { if (unsubscribe) unsubscribe(); });

  function displayData(tableData) {
    if (tableData) {
      columnNames = Object.keys(tableData[0]);
      columnNames.forEach((name) => {
        if (!(name in columnWidths)) {
          columnWidths[name] = 100;
        }  // default width of 100 px
      });
      dataToDisplay = tableData.map((row, rowIndex) => ({
        row: Object.entries(row).map(([key, value]) => ({ colId: key, value })),
        rowId: rowIndex + 1,
      }));
    }
  }

  // if the sheetData is updated, change the tableView and note if we reached the end of data
  $: if ($sheetData && $selectedTable in $sheetData) {
    const tabData = $sheetData[$selectedTable];
    if (tabData.rows.length > 0) {  // extra safety mechanism to avoid empty tables
      tableView.set(tabData.rows);
    }
  }

  $: formattedColumns = columnNames.map(col => {
    const tabColName = `${$selectedTable}.${col}`;
    let colorClass = 'teal-500';
    cellColors[col] = 'white';

    if ($pickedColumns[tabColName]?.color) {
      let color = $pickedColumns[tabColName].color;
      switch (color) {
        case 'sky':
          cellColors[col] = 'sky-200'; break;
        case 'emerald':
          cellColors[col] = 'emerald-200'; break;
        case 'cyan':
          cellColors[col] = 'cyan-200'; break;
        default:
          cellColors[col] = `${color}-300`;
      }
      colorClass = `${color}-500`;
    }
    return { col, colorClass };
  });

  function pickRegion(colName) {
    if ($activatedItem.length > 0 && $currentFlow) {
      if ($currentFlow === 'Select(analyze)') {
        // selecting other existing increases count, selecting self does nothing
        pickAnalyzeRegion(colName);
      } else if ($currentFlow.startsWith('Transform')) {
        // selecting other existing does nothing, selecting self will remove it
        pickMergeRegion(colName);
      }
    }
  }

  function pickMergeRegion(colName) {
    // Prevent user from selecting columns from different tables
    const existingTables = Object.keys($pickedColumns).map(tabCol => tabCol.split('.')[0]);
    if (existingTables.length > 0 && !existingTables.includes($selectedTable)) {
      let warningMessage = 'Selected columns must come from the same table. Please remove other columns first before proceeding.';
      displayAlert('warning', warningMessage);
      return;
    }

    const [varName, position] = $activatedItem.split('_');
    const constraint = $panelVariables[varName][position];
    let prevTabCol = `${constraint.tab}.${constraint.col}`;
    let currTabCol = `${$selectedTable}.${colName}`;

    // If you select the same column, then it becomes de-selected
    if (currTabCol === prevTabCol) {
      pickedColumns.update(pc => {
        delete pc[prevTabCol];
        return pc;
      });
      constraint.col = '';
    } else {
      if (currTabCol in $pickedColumns) {
        return;   // If you choose something that is already picked, do nothing
      } else {    // Otherwise, successfully add the new column to pickedColumns
        pickedColumns.update(pc => {
          delete pc[prevTabCol];
          pc[currTabCol] = { color: 'N/A', count: 1 };
          return pc;
        });
        constraint.tab = $selectedTable;
        constraint.col = colName;
      }
    }

    panelVariables.update(vars => {
      vars[varName][position] = constraint;
      return vars;
    });
    // activatedItem.set(''); Reset the activatedItem
  }

  function pickAnalyzeRegion(colName) {
    // Parse the activatedItem to get the variable name, position, and clause
    const [varName, position] = $activatedItem.split('_');
    const clause = $panelVariables[varName][position];

    // Early exit if the same column is selected
    let prevTabCol = `${clause.tab}.${clause.col}`;
    let currTabCol = `${$selectedTable}.${colName}`;
    if (currTabCol === prevTabCol) { return; }

    // Update the clause with the new table and column
    clause.tab = $selectedTable;
    clause.col = colName;
    panelVariables.update(vars => {
      vars[varName][position] = clause;
      return vars;
    });

    // Remove the previous tabCol item
    let previousColor;
    pickedColumns.update(pc => {
      if (pc[prevTabCol].count === 1) {
        previousColor = pc[prevTabCol].color;
        delete pc[prevTabCol];
      } else {
        pc[prevTabCol].count -= 1;
        previousColor = 'N/A'
      }
      return pc;
    });

    // if it is already in pickedColumns, increment the count by 1
    pickedColumns.update(pc => {
      if ( pc[currTabCol] ) {
        pc[currTabCol].count += 1;
      } else { // otherwise set the color and a new count
        pc[currTabCol] = { color: previousColor, count: 1 };
      };
      return pc;
    });
  }

  let isResizing = false;
  let activelyResizingColumn = null;
  let startX = 0;

  function startResize(event, colName) {
    isResizing = true;
    activelyResizingColumn = colName;
    startX = event.clientX;
    document.addEventListener('mousemove', resizeColumn);
    document.addEventListener('mouseup', stopResize);
  }
  function resizeColumn(event) {
    if (!isResizing) return;
    const dx = event.clientX - startX;
    columnWidths[activelyResizingColumn] += dx;
    startX = event.clientX;
  }
  function stopResize() {
    isResizing = false;
    document.removeEventListener('mousemove', resizeColumn);
    document.removeEventListener('mouseup', stopResize);
  }

  function autoResize(colName) {
    // Change table layout to auto
    const table = document.querySelector('table');
    table.style.tableLayout = 'auto';
    // Remove width style from the column we want to auto-resize
    const headerCell = document.querySelector(`th[data-id="${colName}"]`);
    headerCell.style.width = '';
    // Force a reflow so browser recalculates
    void table.offsetHeight;

    // Get the width of the header and body cells
    const headerWidth = parseInt(window.getComputedStyle(headerCell).width);
    const rowsToConsider = Math.min(128, dataToDisplay.length);
    let bodyWidth = 0;
    for (let i = 0; i < rowsToConsider; i++) {
      const bodyCell = document.querySelector(`td[data-id="${colName}-${dataToDisplay[i].rowId}"]`);
      const cellWidth = parseInt(window.getComputedStyle(bodyCell).width);
      if (cellWidth > bodyWidth) {
        bodyWidth = cellWidth;
      }
    }
    // Revert back to table-layout: fixed and set the final captured width
    const finalWidth = `${Math.min(Math.max(headerWidth, bodyWidth), 1024)}px`;
    table.style.tableLayout = 'fixed';
    headerCell.style.width = finalWidth;
    columnWidths[colName] = parseInt(finalWidth);
  }
</script>

<div class="border-gray-200 border mt-1 lg:mt-2 inline-block w-auto table-region max-h-full overflow-y-auto"
    transition:fade={{ duration: 400 }} bind:this={tableRegion}>
  <table class="cursor-pointer text-sm text-left text-gray-500 table-fixed w-full">
    <thead class="text-gray-50 h-8">
      <tr> {#each formattedColumns as { col, colorClass }}
        <th class={`whitespace-normal relative px-2 text-clip sticky top-0 z-10 bg-${colorClass}`}
          scope="col" data-id={col} on:click={() => pickRegion(col)} style={`width: ${columnWidths[col]}px`}>
          {col}
          <div class="absolute top-0 bottom-0 right-0 w-0.5 bg-stone-400 cursor-col-resize
            opacity-50 hover:opacity-100 hover:w-1 z-10" on:mousedown={(e) => startResize(e, col)} 
            on:click|stopPropagation on:dblclick|stopPropagation={() => autoResize(col)}/>
        </th>
        {/each}
      </tr>
    </thead>

    <tbody>
      {#each dataToDisplay as { row, rowId } (rowId)}
        <tr class="border-b bg-white h-7">
          {#each row as { colId, value }}
            <td data-id={`${colId}-${rowId}`} class={`whitespace-nowrap overflow-hidden text-clip border-r px-3 cursor-default relative bg-${cellColors[colId]}`} on:click={() => pickRegion(colId)}>
              {value}
            </td>
          {/each}
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<!-- To prevent Tailwind CSS purging. Do not remove: 
  bg-amber-300 bg-sky-200 bg-emerald-200 bg-rose-300 bg-violet-300 bg-orange-300 bg-green-300 bg-cyan-200 bg-fuchsia-300
  bg-amber-500 bg-sky-500 bg-emerald-500 bg-rose-500 bg-violet-500 bg-orange-500 bg-green-500 bg-cyan-500 bg-fuchsia-500
-->
<div class="text-center py-2">
  <p class="text-gray-600 text-sm">
    Please complete or cancel your current task in order to load more data.
  </p>
</div>