<script>
  import { fade, slide } from 'svelte/transition';
  import { getSortFunction, copy, paste } from './tableUtils.js';
  import { createEventDispatcher } from 'svelte';
  import { onMount, onDestroy } from 'svelte';
  import { searchQuery } from '@store';
  import { pushEdit, popEdit } from '@store';
  // Props
  export let data = [];
  export let columns = [];
  export let editable = true;
  export let sortable = true;
  export let searchable = true;
  export let resizable = true;
  export let infiniteScroll = true;
  export let onDataFetch = null;
  export let onCellEdit = null;
  export let className = '';
  export let headerColor = 'bg-teal-500';
  export let anchorCells = new Set();

  // State
  let tableRegion;
  let columnWidths = {};
  let numberOfRows = 0;
  let dataToDisplay = [];
  let selectedCell = '';
  let cellCoordinates = null;
  let editCoordinates = { col: '', row: -1 };
  let isEditing = false;
  let isWriting = false;
  let isLoading = false;
  let isDataEnd = false;
  let endMessageTriggered = false;
  let foundCells = new Set();
  let sortConfig = { columns: [], direction: 'none' };
  let originalToSorted = {};
  let sortedToOriginal = {};
  let novelContent = '';
  let originalContent = '';

  // Selection state
  let selection = { start: null, end: null };
  let isSelecting = false;

  // Event dispatcher
  const dispatch = createEventDispatcher();

  // Common methods
  function displayData(tableData) {
    if (!tableData?.length) return;

    columns = Object.keys(tableData[0]);
    columns.forEach(name => {
      if (!(name in columnWidths)) {
        columnWidths[name] = 100;
      }
    });

    numberOfRows = tableData.length;

    dataToDisplay = tableData.map((row, rowIndex) => ({
      row: Object.entries(row).map(([key, value]) => ({ colId: key, value })),
      rowId: rowIndex + 1,
      isVisible: true
    }));
  }
  
  function navigateTo(event) {
    if (isEditing || isWriting) return;

    if (cellCoordinates) {
      if (event.preventDefault) {
        event.preventDefault();
      }

      if ((event.ctrlKey || event.metaKey) && event.key === 'c') {
        copySelectedCells();
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
    let sortedRowIndex = originalToSorted[rowIndex] || rowIndex; // Sorted row for display
    let colIndex = columns.indexOf(colId);

    if (jumpToEnd) {
      switch (event.key) {
        case 'ArrowUp':
          sortedRowIndex = 1;
          rowIndex = sortedToOriginal[sortedRowIndex] || sortedRowIndex;
          break;
        case 'ArrowDown':
          sortedRowIndex = numberOfRows;
          rowIndex = sortedToOriginal[sortedRowIndex] || sortedRowIndex;
          break;
        case 'ArrowLeft':
          colIndex = 0;
          break;
        case 'ArrowRight':
          colIndex = columns.length - 1;
          break;
      }
    } else {
      // Navigate in sorted order if sorting exists
      switch (event.key) {
        case 'ArrowUp':
          sortedRowIndex = nextVisibleRow(sortedRowIndex, 'ArrowUp');
          rowIndex = sortedToOriginal[sortedRowIndex] || sortedRowIndex;
          break;
        case 'ArrowDown':
          sortedRowIndex = nextVisibleRow(sortedRowIndex, 'ArrowDown');
          rowIndex = sortedToOriginal[sortedRowIndex] || sortedRowIndex;
          break;
        case 'ArrowLeft':
          colIndex = colIndex > 0 ? colIndex - 1 : colIndex;
          break;
        case 'ArrowRight':
          colIndex = colIndex < columns.length - 1 ? colIndex + 1 : colIndex;
          break;
      }
    }
    selectRegion(columns[colIndex], rowIndex);
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
      const rowIndex = originalToSorted[rawId] - 1 || rawId - 1; // Handle sorting and off-by-one
      const cellData = dataToDisplay[rowIndex].row.find((cell) => cell.colId === colIndex);

      if (cellData) {
        cellData.value = novelContent;
        storeEditHistory(rowIndex, colIndex);
        
        // Dispatch cellEdit event
        dispatch('cellEdit', {
          coordinates: { row: rowIndex, col: colIndex },
          newData: dataToDisplay
        });
        
        // Call onCellEdit callback if provided
        if (onCellEdit) {
          onCellEdit({
            coordinates: { row: rowIndex, col: colIndex },
            newData: dataToDisplay
          });
        }
      }
      dataToDisplay = [...dataToDisplay]; // Force Svelte to recognize the change
    }

    resetTable({ content: true, selection: false });
    selection = { start: null, end: null }
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
    selection = { start: null, end: null };
  }

  function autoResize(colName) {
    if (!resizable) return;
    
    const table = tableRegion.querySelector('table');
    table.style.tableLayout = 'auto';
    
    const headerCell = tableRegion.querySelector(`th[data-id="${colName}"]`);
    headerCell.style.width = '';
    void table.offsetHeight;

    const headerWidth = parseInt(window.getComputedStyle(headerCell).width);
    const rowsToConsider = Math.min(128, dataToDisplay.length);
    let bodyWidth = 0;
    
    for (let i = 0; i < rowsToConsider; i++) {
      const bodyCell = tableRegion.querySelector(`td[data-id="${colName}-${dataToDisplay[i].rowId}"]`);
      const cellWidth = parseInt(window.getComputedStyle(bodyCell).width);
      if (cellWidth > bodyWidth) {
        bodyWidth = cellWidth;
      }
    }
    
    const finalWidth = `${Math.min(Math.max(headerWidth, bodyWidth), 1024)}px`;
    table.style.tableLayout = 'fixed';
    headerCell.style.width = finalWidth;
    columnWidths[colName] = parseInt(finalWidth);
  }

  $: {
    if (searchable) {
      foundCells.clear();
      dataToDisplay.forEach((rowData) => {
        let rowHasMatchingCell = false;

        rowData.row.forEach((cellData) => {
          if ($searchQuery) {
            const queryText = $searchQuery.toLowerCase();
            if (cellData.value.toString().toLowerCase().includes(queryText)) {
              foundCells.add(`${cellData.colId}-${rowData.rowId}`);
              rowHasMatchingCell = true;
            }
          }
        });
        // Mark the row as visible if at least one cell matches the search query
        rowData.isVisible = !$searchQuery || rowHasMatchingCell;
      });
      dataToDisplay = dataToDisplay.slice(); // Force Svelte to recognize the change
    }
  }

  // Column resizing
  let isResizing = false;
  let activelyResizingColumn = null;
  let startX = 0;

  function startResize(event, colName) {
    if (!resizable) return;
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

  // Infinite scroll
  function handleScroll(event) {
    if (!infiniteScroll || !onDataFetch) return;
    
    if (tableRegion.scrollTop + tableRegion.clientHeight >= tableRegion.scrollHeight - 10) {
      if (!isLoading) {
        isLoading = true;
        onDataFetch().then((hasMoreData) => {
          isLoading = false;
          if (!hasMoreData && !endMessageTriggered) {
            isDataEnd = true;
            setTimeout(() => {
              isDataEnd = false;
              endMessageTriggered = true;
            }, 4000);
          }
        });
      }
    }
  }

  // Lifecycle
  onMount(() => {
    window.addEventListener('keydown', navigateTo);
    document.addEventListener('click', handleClick);
    if (infiniteScroll) {
      tableRegion?.addEventListener('scroll', handleScroll);
    }
  });

  onDestroy(() => {
    window.removeEventListener('keydown', navigateTo);
    document.removeEventListener('click', handleClick);
    if (infiniteScroll) {
      tableRegion?.removeEventListener('scroll', handleScroll);
    }
  });

  // Reactivity
  $: if (data) {
    displayData(data);
  }

  $: if (sortConfig.columns.length > 0) {
    const sortFunctions = sortConfig.columns.map(getSortFunction);
    dataToDisplay = [...dataToDisplay].sort((a, b) => {
      for (const sortFn of sortFunctions) {
        const result = sortFn(a, b);
        if (result !== 0) return result;
      }
      return 0;
    });
  }

  function sortTable(colName) {
    if (!sortable) return;
    
    const existingColumn = sortConfig.columns.find((c) => c.column === colName);
    let newDirection = existingColumn ? 
      (existingColumn.direction === 'asc' ? 'desc' : 'none') : 'asc';

    if (newDirection === 'none') {
      sortConfig.columns = sortConfig.columns.filter((c) => c.column !== colName);
    } else {
      if (existingColumn) {
        existingColumn.direction = newDirection;
      } else {
        sortConfig.columns = [...sortConfig.columns, { column: colName, direction: newDirection }];
      }
    }
    
    sortConfig = sortConfig; // Trigger reactivity
  }

  function selectRegion(colName, rowId, isSelectionStart = false) {
    if (isSelectionStart) {
      selection = { start: { col: colName, row: rowId }, end: { col: colName, row: rowId } };
    } else if (selection.start) {
      selection.end = { col: colName, row: rowId };
    }

    cellCoordinates = { col: colName, row: rowId };
    selectedCell = `${colName}-${rowId}`;

    dispatch('cellClick', { col: colName, row: rowId });

    const currentCell = document.querySelector(`[data-id="${selectedCell}"]`);
    const tableContainer = document.querySelector('#full-table');

    if (rowId < 2 && tableContainer) {
      tableContainer.scrollTop = 0;
    } else if (currentCell) {
      currentCell.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
    }
  }

  function isCellSelected(colName, rowId) {
    if (!selection.start || !selection.end) return false;
    
    const startCol = columns.indexOf(selection.start.col);
    const endCol = columns.indexOf(selection.end.col);
    const startRow = selection.start.row;
    const endRow = selection.end.row;
    
    const colIndex = columns.indexOf(colName);
    return colIndex >= Math.min(startCol, endCol) && 
           colIndex <= Math.max(startCol, endCol) && 
           rowId >= Math.min(startRow, endRow) && 
           rowId <= Math.max(startRow, endRow);
  }

  function copySelectedCells() {
    if (!selection.start || !selection.end) return;

    const startCol = columns.indexOf(selection.start.col);
    const endCol = columns.indexOf(selection.end.col);
    const startRow = selection.start.row;
    const endRow = selection.end.row;

    const minCol = Math.min(startCol, endCol);
    const maxCol = Math.max(startCol, endCol);
    const minRow = Math.min(startRow, endRow);
    const maxRow = Math.max(startRow, endRow);

    const selectedData = [];
    for (let row = minRow; row <= maxRow; row++) {
      const rowData = [];
      for (let col = minCol; col <= maxCol; col++) {
        const cell = dataToDisplay[row - 1]?.row.find(c => c.colId === columns[col]);
        rowData.push(cell?.value ?? '');
      }
      selectedData.push(rowData.join('\t'));
    }

    navigator.clipboard.writeText(selectedData.join('\n'));
  }

  function handleMouseDown(event, colName, rowId) {
    if (event.button === 0) {
      isSelecting = true;
      selectRegion(colName, rowId, true);
    }
  }

  function handleMouseMove(event, colName, rowId) {
    if (isSelecting) {
      selectRegion(colName, rowId);
    }
  }

  function handleMouseUp() {
    isSelecting = false;
  }

  function handleClick(event) {
    if (!event.target.closest('.table-region')) {
      selectedCell = '';
      cellCoordinates = null;
      selection = { start: null, end: null };
    }
  }
</script>

<div id="full-table" class="border-gray-200 border mt-1 lg:mt-2 inline-block w-auto max-h-full overflow-y-auto table-region {className}"
    transition:fade={{ duration: 400 }} bind:this={tableRegion}
    on:mouseup={handleMouseUp}>
  <table class="text-sm text-left text-gray-500 table-fixed w-full">
    <thead class="text-gray-50 h-8">
      <tr>
        <slot name="rowPrefix" />
        {#each columns as col}
          <th class="whitespace-normal {headerColor} relative px-2 text-clip sticky top-0 z-10"
            scope="col" data-id={col} style={`width: ${columnWidths[col]}px`}>
            <span class="cursor-pointer" on:click={() => sortTable(col)}>{col}</span>
            {#if sortConfig.columns.some((c) => c.column === col && c.direction === 'asc')}
              ▲
            {:else if sortConfig.columns.some((c) => c.column === col && c.direction === 'desc')}
              ▼
            {/if}
            {#if resizable}
              <div class="absolute top-0 bottom-0 right-0 w-0.5 bg-stone-400 cursor-col-resize
                opacity-50 hover:opacity-100 hover:w-1 z-10" 
                on:mousedown={(e) => startResize(e, col)}
                on:click|stopPropagation 
                on:dblclick|stopPropagation={() => autoResize(col)}/>
            {/if}
          </th>
        {/each}
      </tr>
    </thead>

    <tbody>
      {#each dataToDisplay as rows (rows.rowId)}
        {#if rows.isVisible}
          <tr transition:slide={{ duration: 600 }} class="border-b bg-white h-7">
            <slot name="rowPrefix" {rows} />
            {#each rows.row as cell (cell.colId)}
              <td data-id={`${cell.colId}-${rows.rowId}`}
                class="whitespace-nowrap overflow-hidden text-clip border-r px-3 cursor-default relative"
                class:selected={selectedCell === `${cell.colId}-${rows.rowId}`}
                class:selected-range={isCellSelected(cell.colId, rows.rowId)}
                class:bg-yellow-100={foundCells.has(`${cell.colId}-${rows.rowId}`) || anchorCells.has(`${cell.colId}-${rows.rowId-1}`)}
                on:mousedown={(e) => handleMouseDown(e, cell.colId, rows.rowId)}
                on:mousemove={(e) => handleMouseMove(e, cell.colId, rows.rowId)}
                on:dblclick={() => editable && activateEditMode(cell.colId, rows.rowId)}
                on:click={() => selectRegion(cell.colId, rows.rowId)}>
                <slot name="cell" {cell} {rows}>
                  {cell.value}
                </slot>
                {#if editable && editCoordinates.row === rows.rowId && editCoordinates.col === cell.colId}
                  <input class="absolute top-0 left-0 h-7 w-full pl-3 pb-1 border-none" 
                    on:blur={saveChanges}
                    bind:value={novelContent} 
                    on:keydown|stopPropagation={handleEditEvents} 
                    autofocus/>
                {/if}
              </td>
            {/each}
          </tr>
        {/if}
      {/each}
    </tbody>
  </table>
</div>

{#if infiniteScroll}
  <div class="text-center py-2">
    <p class="text-gray-600 text-sm">
      {#if isLoading}
        Loading more data...
      {:else if isDataEnd}
        You've reached the end!
      {/if}
    </p>
  </div>
{/if}

<style>
  .selected {
    border: 2px solid #0c5cd3;
  }
  .selected-range {
    background-color: rgba(12, 92, 211, 0.1);
    border: 1px solid #0c5cd3;
  }
</style>