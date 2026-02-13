<script>
  import { tempData, sheetData } from '@store';
  import BaseTable from './BaseTable.svelte';
  import { onDestroy } from 'svelte';

  let tableData = [];

  // Subscribe to tableStore for derived data
  $: if ($tempData) {
    const derivedData = $tempData.rows;
    if (derivedData?.length > 0) {
      tableData = derivedData;
    }
  }

  // Cleanup temp data on destroy
  onDestroy(() => {
    if ($tempData && $tempData.name) {
      sheetData.update(currentSheet => {
        if (currentSheet[$tempData.name]) {
          delete currentSheet[$tempData.name];
        }
        return currentSheet;
      });
    }
  });
</script>

<BaseTable
  data={tableData}
  editable={false}
  sortable={true}
  searchable={true}
  resizable={true}
  infiniteScroll={false}
  headerColor="bg-cyan-500"
/>
