<script>
  import { tableView, pushEdit, popEdit } from '@store';
  import { selectedTable, sheetData, tabSwitchTrigger, tableStore } from '@store';  // from dataStore
  import { onDestroy, onMount } from 'svelte';
  import { fade, slide } from 'svelte/transition';
  import { copy, paste } from './tableUtils.js';
  import AnchorButtons from './anchors.svelte';

  let tableRegion;
  let columnNames = [];
  let dataToDisplay = [];
  let numberOfRows = 0;

  let selectedCell = '';
  let cellCoordinates = null;
  let editCoordinates = { col: '', row: -1 };
  let anchorCells;  // array of string coordinates, written as 'colId-rowId'
  let anchorRows;   // array of integer row-ids which serve as anchor points

  let isEditing = false;
  let isWriting = false;
  let unsubscribe;

  onMount(() => {
    // unsubscribe = tableView.subscribe(displayData);
    unsubscribe = tableStore.subscribe(({ tableData, tableType }) => {
      displayData(tableData, tableType);
    });
    window.addEventListener('keydown', navigateTo);
    document.addEventListener('click', handleClick);
  });
  onDestroy(() => {
    if (unsubscribe) unsubscribe();
    window.removeEventListener('keydown', navigateTo);
    document.removeEventListener('click', handleClick);
  });

  function displayData(tableData, tableType) {
    if (tableType === 'dynamic' && tableData) {
      columnNames = Object.keys(tableData[0]);
      numberOfRows = tableData.length;

      dataToDisplay = tableData.map((row, rowIndex) => {
        let transformedRow = Object.entries(row).map(([key, value]) => {
          return { colId: key, value: value };
        });
        let rowVisible = $sheetData[$selectedTable].visibility.get(rowIndex)
        return { row: transformedRow, rowId: rowIndex + 1, isVisible: rowVisible };
      });
    }
  }

  function handleClick(event) {
    if (isEditing || isWriting || selectedCell.length > 0) {
      if (!tableRegion.contains(event.target)) {
        resetTable({ content: true, selection: true });
      }
    }
  }

  // if the sheetData is updated, change the tableView and note if we reached the end of data
  $: if ($sheetData && $selectedTable in $sheetData) {
    const currentTable = $sheetData[$selectedTable];
    if (currentTable.rows.length > 0) {  // extra safety mechanism to avoid empty tables
      tableView.set(currentTable.rows);
    }
    anchorCells = currentTable.anchorPoints.map(point => `${point[0]}-${point[1]}`);
    anchorRows = currentTable.anchorPoints.map(point => point[1]);
  }
  $: if ($tabSwitchTrigger && tableRegion) {
    tableRegion.scrollTop = 0; // to avoid immediately fetching data on tab switch
  }

  function resetTable({ content = false, selection = false } = {}) {
    isEditing = false;
    isWriting = false;
    editCoordinates = { col: '', row: -1 };

    if (content) {
      originalContent = '';
      novelContent = '';
    }
    if (selection) {
      cellCoordinates = null;
      selectedCell = '';
    }
  }

  function navigateTo(event) {
    if (isEditing || isWriting) return; // Ignore key presses when editing or writing

    if (cellCoordinates) {
      if (event.preventDefault) {
        event.preventDefault();
      }

      if ((event.ctrlKey || event.metaKey) && event.key === 'c') {
        copy(cellCoordinates, dataToDisplay);
        return;
      } else if ((event.ctrlKey || event.metaKey) && event.key === 'v') {
        paste(cellCoordinates, dataToDisplay).then(newData => { dataToDisplay = newData; });
        return;
      } else if ((event.ctrlKey || event.metaKey) && event.key === 'z') {
        undo();
        return;
      } else if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(event.key)) {
        arrowNavigation(event);
      } else {
        keyboardNavigation(event);
      }
    }
  }

  function keyboardNavigation(event) {
    switch (event.key) {
      case 'Tab':
        event.preventDefault(); // Prevents the default tab behavior
        navigateTo({ key: 'ArrowRight' });
        break;

      case 'Backspace':
      case 'Delete':
        activateEditMode(cellCoordinates.col, cellCoordinates.row, true);
        novelContent = ''; // empty the cell contents
        break;

      case 'Enter':
        activateEditMode(cellCoordinates.col, cellCoordinates.row);
        break;

      default: // If alphanumeric
        if (/^[a-zA-Z0-9]$/.test(event.key)) {
          activateEditMode(cellCoordinates.col, cellCoordinates.row, true);
          novelContent = event.key; // Initialize the novelContent with the pressed key
        }
    }
  }

  function arrowNavigation(event) {
    const jumpToEnd = event.metaKey || event.ctrlKey; // Check for Cmd (Mac) or Ctrl (Windows) key
    let { row: rowIndex, col: colId } = cellCoordinates;
    let colIndex = columnNames.indexOf(colId);

    if (jumpToEnd) {
      switch (event.key) {
        case 'ArrowUp':
          rowIndex = 1;
          break;
        case 'ArrowDown':
          rowIndex = numberOfRows;
          break;
        case 'ArrowLeft':
          colIndex = 0;
          break;
        case 'ArrowRight':
          colIndex = columnNames.length - 1;
          break;
      }
    } else {
      switch (event.key) {
        case 'ArrowUp':
          rowIndex = nextVisibleRow(rowIndex, 'ArrowUp');
          break;
        case 'ArrowDown':
          rowIndex = nextVisibleRow(rowIndex, 'ArrowDown');
          break;
        case 'ArrowLeft':
          colIndex = colIndex > 0 ? colIndex - 1 : colIndex;
          break;
        case 'ArrowRight':
          colIndex = colIndex < columnNames.length - 1 ? colIndex + 1 : colIndex;
          break;
      }
    }
    selectRegion(columnNames[colIndex], rowIndex);
  }

  function nextVisibleRow(currentIndex, direction) {
    if (direction === 'ArrowDown') {
      for (let i = currentIndex + 1; i <= numberOfRows; i++) {
        if (dataToDisplay[i - 1].isVisible) return i;
      }
    } else if (direction === 'ArrowUp') {
      for (let i = currentIndex - 1; i >= 1; i--) {
        if (dataToDisplay[i - 1].isVisible) return i;
      }
    }
    return currentIndex; // If no visible row is found, return the current index
  }

  function selectRegion(colName, rowId) {
    cellCoordinates = { col: colName, row: rowId };
    selectedCell = `${colName}-${rowId}`;

    const currentCell = document.querySelector(`[data-id="${selectedCell}"]`);
    const tableContainer = document.querySelector('#full-table');

    if (rowId < 2 && tableContainer) {
      tableContainer.scrollTop = 0;
    } else if (currentCell) {
      currentCell.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
    }
  }

  let originalContent = ''; // To store original content during editing
  let novelContent = ''; // To store new, edited content during editing
  function activateEditMode(colName, rowId, writing = false) {
    const row = dataToDisplay.find((r) => r.rowId === rowId);
    const cell = row.row.find((c) => c.colId === colName);

    if (cell) {
      originalContent = cell.value;
      novelContent = originalContent;
    }
    isEditing = true;
    isWriting = writing;
    editCoordinates = { col: colName, row: rowId };
  }

  function saveChanges() {
    const { row: rawId, col: colIndex } = editCoordinates;

    if (rawId > 0 && colIndex.length > 0) {
      const rowIndex = rawId - 1;
      const cellData = dataToDisplay[rowIndex].row.find((cell) => cell.colId === colIndex);

      if (cellData) {
        cellData.value = novelContent;
        storeEditHistory(rowIndex, colIndex);
      }
      dataToDisplay = [...dataToDisplay]; // Force Svelte to recognize the change
    }

    resetTable({ content: true, selection: false });
  }

  function storeEditHistory(row, col) {
    const changeType = novelContent.length === 0 ? 'clearCell' : 'updateCell';

    // Update the editHistory with the changed data
    pushEdit({
      type: changeType,
      row: row,
      col: col,
      originalValue: originalContent,
      newValue: novelContent,
      timestamp: new Date().toISOString(), // ISO string format of the current time
    });
  }

  function undo() {
    const lastAction = popEdit();
    if (!lastAction) return; // Return immediately if there is no previous action

    const cellData = dataToDisplay[lastAction.row].row.find(
      (cell) => cell.colId === lastAction.col
    );
    if (cellData) {
      cellData.value = lastAction.originalValue;
      dataToDisplay = [...dataToDisplay];
      selectRegion(lastAction.col, lastAction.row + 1);
    }
  }

  function handleEditEvents(event) {
    const currentInput = event.target;
    const cursorPosition = currentInput.selectionStart;
    event.stopPropagation();

    switch (event.key) {
      // Delete and Up/Down/Left/Right all follow default input box behavior, no need to handle
      case 'Enter':
        saveChanges();
        navigateTo({ key: 'ArrowDown' });
        break;
      case 'Tab':
        event.preventDefault(); // Prevents the default tab behavior
        saveChanges();
        navigateTo({ key: 'ArrowRight' });
        break;
      case 'Escape':
        // Revert the value to the original value
        resetTable({ content: true, selection: false });
        break;

      case 'ArrowLeft':
      case 'ArrowRight':
      case 'ArrowUp':
      case 'ArrowDown':
        if (isWriting) {
          saveChanges();
          navigateTo(event);
        }
    }
  }
</script>

<div class="mt-1 lg:mt-2 inline-block table-region max-h-full overflow-y-auto"
    transition:fade bind:this={tableRegion}>
  <table class="text-sm text-left text-gray-500 table-fixed">
    <thead class="text-gray-50 h-8">
      <tr>
        <th></th> <!-- Empty header for alignment with the toggle buttons -->
        {#each columnNames as col}
          <th class="whitespace-normal bg-teal-500 relative px-2 text-clip sticky"
            scope="col" data-id={col}>{col}
          </th>
        {/each}
      </tr>
    </thead>

    <tbody>
      {#each dataToDisplay as rows (rows.rowId)}
        {#if rows.isVisible}
        <tr transition:slide={{ duration: 600 }} class="border-b bg-white h-7">
          <AnchorButtons {rows} {numberOfRows} {anchorRows} />
          {#each rows.row as cell (cell.colId)}
            <td data-id={`${cell.colId}-${rows.rowId}`}
              class="whitespace-nowrap overflow-hidden text-clip border-r px-3 cursor-default relative"
              class:selected={selectedCell === `${cell.colId}-${rows.rowId}`}
              class:bg-yellow-100={anchorCells.includes(`${cell.colId}-${rows.rowId-1}`)}
              on:dblclick={() => activateEditMode(cell.colId, rows.rowId)}
              on:click={() => selectRegion(cell.colId, rows.rowId)}>
              {cell.value}
              <!-- Input Overlay for editing content -->
              {#if editCoordinates.row === rows.rowId && editCoordinates.col === cell.colId}
                <input class="absolute top-0 left-0 h-7 w-full pl-3 pb-1 border-none" on:blur={saveChanges} 
                    bind:value={novelContent} on:keydown|stopPropagation={handleEditEvents} autofocus/>
              {/if}
            </td>
          {/each}
        </tr>
        {/if}
      {/each}
    </tbody>
  </table>
</div>

<style>
  .selected {   /*  dark blue  */
    border: 2px solid #0c5cd3;
  }
</style>