<script>
  import { tableView, selectedTable, sheetData, fetchData } from '@store';
  import BaseTable from './BaseTable.svelte';
  import { onMount, onDestroy } from 'svelte';

  let tableData = [];
  let unsubscribe;

  // Subscribe to tableView for reactivity
  onMount(() => {
    unsubscribe = tableView.subscribe(data => {
      tableData = data || [];
    });
  });
  onDestroy(() => { if (unsubscribe) unsubscribe(); });

  // Keep tableView in sync with sheetData
  $: if ($sheetData && $selectedTable in $sheetData) {
    const tabData = $sheetData[$selectedTable];
    if (tabData.rows?.length > 0) {
      tableView.set(tabData.rows);
    }
  }

  // Handle data fetching
  async function handleDataFetch() {
    const currentTable = $selectedTable;
    await fetchData(currentTable);
    return $sheetData[currentTable]?.hasMoreData ?? true;
  }
  
  function handleCellEdit(event) {
    const data = event.detail || event;
    const { newData } = data;
    // Convert BaseTable's internal format back to plain row objects
    const plainRows = newData.map(rowObj => {
      const row = {};
      rowObj.row.forEach(cell => {
        row[cell.colId] = cell.value;
      });
      return row;
    });
    tableView.set(plainRows);
  }
</script>

<BaseTable
  data={tableData}
  editable={true}
  sortable={true}
  searchable={true}
  resizable={true}
  infiniteScroll={true}
  onDataFetch={handleDataFetch}
  onCellEdit={handleCellEdit}
  on:cellEdit={handleCellEdit}
/>