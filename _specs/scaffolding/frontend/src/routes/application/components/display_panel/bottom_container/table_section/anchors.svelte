<script>
  import { selectedTable, sheetData } from '@store';  // from dataStore
  import { onDestroy, onMount } from 'svelte';

  export let rows;
  export let numberOfRows;
  export let anchorRows;

  function determineSegment(rowId, direction, lastFetchedRow) {
    let start, end;
    if (direction === 'above') {
      start = [...anchorRows].reverse().find(r => r < rowId - 1) + 1 || 1;
      end = rowId - 2;
    } else if (direction === 'below') {
      start = rowId;
      end = anchorRows.find(r => r > rowId) - 1 || lastFetchedRow;
    }
    return Array.from({ length: end - start + 1 }, (_, i) => i + start);
  }

  function toggleSegment(rowId, direction) {
    const currentTable = $sheetData[$selectedTable];
    let segment = determineSegment(rowId, direction, currentTable.lastFetchedRow);

    sheetData.update(currentSheet => {
      segment.forEach(rowIdx => {
        currentTable.visibility.set(rowIdx, !currentTable.visibility.get(rowIdx));
      });
      return currentSheet;
    });
  }
</script>

<!-- goes outside the anchor span to keep the extra left column permanently present -->
<td class="whitespace-nowrap border">
  {#if anchorRows.includes(rows.rowId-1)}
    <!-- AnchorPoint buttons to manage rows -->
    <span class="flex flex-col items-center toggle-buttons">

      <!-- Expand/Collapse Up -->
      {#if rows.rowId > 1}
      <button class="hover:bg-teal-400" on:click={() => toggleSegment(rows.rowId, 'above')}>
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="4 3 12 12" fill="currentColor" class="w-5 h-3">
          <path fill-rule="evenodd" d="M9.47 6.47a.75.75 0 0 1 1.06 0l4.25 4.25a.75.75 0 1 1-1.06 1.06L10 8.06l-3.72 3.72a.75.75 0 0 1-1.06-1.06l4.25-4.25Z" clip-rule="evenodd" />
        </svg>                
      </button>
      {/if}

      <!-- Expand/Collapse Down -->
      {#if rows.rowId !== numberOfRows}
      <button class="hover:bg-teal-400" on:click={() => toggleSegment(rows.rowId, 'below')}>
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="4 5 12 12" fill="currentColor" class="w-5 h-3">
          <path fill-rule="evenodd" d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06Z" clip-rule="evenodd" />
        </svg>
      </button>
      {/if}
      <!-- min-x, min-y, width and height -->
    </span>         
  {/if}
</td>
