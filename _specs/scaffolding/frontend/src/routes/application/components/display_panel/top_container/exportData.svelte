<script lang="ts">
  import { displayAlert } from '@alert';
  import { selectedSpreadsheet, selectedTable, serverUrl, receiveData, displayLayout, saveEdits, exportView } from '@store';
  import { securedFetch } from '$lib/apiUtils';
  import spinningLogo from '@assets/spinner.gif';
  import AlertBox from '../../shared/alertBox.svelte';
  import SelectedIcon from '@lib/icons/Selected.svelte'
  import InteractivePanel from './stages/components/interactiveComp.svelte';

  let exportOption = 'csv';
  let fileName = '';
  let isLoading = false;
  let currentTab = $selectedTable;
  let currentSpreadsheet = $selectedSpreadsheet.ssName.replace(/\s/g, '_');

  // Reactively update the file name based on the selected export option
  $: {
    const dateString = new Date().toISOString().split('T')[0].replace(/-/g, '_');
    const prefix = exportOption === 'xlsx' ? currentSpreadsheet : `${currentTab}_export`;
    fileName = `${prefix}_${dateString}.${exportOption}`;
  }

  const handleCancel = () => {
    currentTab = null;
    exportView.set(false);
    displayLayout.set('bottom');
    displayAlert('info', 'Export cancelled');
  }

  async function handleExport() {
    if (!fileName.trim()) {
      displayAlert('warning', 'Please enter a file name'); return;
    }
    if (fileName.length > 64) {
      displayAlert('warning', 'File name cannot exceed 64 characters'); return;
    }

    isLoading = true;
    saveEdits();  // Save any pending edits before exporting
    const payload = { 
      sheetName: $selectedSpreadsheet.ssName,
      tabName: currentTab, 
      exportType: exportOption,
      fileName: fileName.trim()
    };

    try {
      const response = await securedFetch(`${serverUrl}/interactions/download`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error('Download failed: ' + data.detail);
      }

      // Get the filename from the Content-Disposition header and prepare the blob
      const disposition = response.headers.get('Content-Disposition');
      const finalFilename = disposition ? disposition.split('filename=')[1].replace(/['"]/g, '') : fileName;
      const exportBlob = await response.blob();
      
      // Create a link element and trigger the download
      const url = window.URL.createObjectURL(exportBlob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = finalFilename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);

      displayAlert('success', `${fileName} has been successfully downloaded`);
      // Wait 5 seconds, then close the export panel
      setTimeout(() => {
        currentTab = null;
        exportView.set(false);
        displayLayout.set('bottom');
      }, 5000);
    } catch (err) {
      console.error(err);
      displayAlert('error', 'An error occurred while downloading the file');
    } finally {
      isLoading = false;
    }
  }
</script>

{#if isLoading}
  <div class="mx-6 p-0 md:p-2 lg:px-4 lg:py-6 box-border flex flex-col justify-between h-full">
    <div>
      <h2 class="font-medium text-xl mb-2">Export Data</h2>
      <p class="italic">Preparing your file for download ...</p>
    </div>

    <div class="flex-grow flex items-center justify-center">
      <img src={spinningLogo} alt="spinningLogo" class="h-56 xl:h-64" />
    </div>
  </div>
{:else}
  <InteractivePanel title="Export Data" subtitle="Choose your download option and enter a file name:"
    onReject={handleCancel} rejectLabel="Cancel"
    onAccept={handleExport} acceptLabel={isLoading ? 'Downloading...' : 'Download'}>

  <div class="text-sm">
    <div class="space-y-2">
      <label class="flex items-center space-x-3">
        <input type="radio" bind:group={exportOption} value="csv" class="form-radio text-blue-600" />
        <span>Download 
          <select bind:value={currentTab} class="ml-1 py-1 rounded-md  form-select text-sm">
            {#each $selectedSpreadsheet.tabNames as tabName}
              {#if tabName[0] !== '('}
                <option value={tabName}>{tabName}</option>
              {/if}
            {/each}
          </select> 
          table as CSV
        </span>
      </label>
      <label class="flex items-center space-x-3">
        <input type="radio" bind:group={exportOption} value="xlsx" class="form-radio text-blue-600" />
        <span>Download entire spreadsheet as XLSX</span>
      </label>
      <label class="flex items-center space-x-3">
        <input type="radio" bind:group={exportOption} value="json" class="form-radio text-blue-600" />
        <span>Export as JSON (for developers)</span>
      </label>
    </div>

     <div class="flex items-center space-x-2 mt-4">
      <label for="fileName" class="text-sm whitespace-nowrap font-medium text-gray-700">File name:</label>
      <input type="text" id="fileName" bind:value={fileName}
        class="mt-1 block w-full text-sm rounded-md border-gray-300 shadow-sm focus:border-blue-300 focus:ring focus:ring-blue-200 focus:ring-opacity-50"/>
    </div>
  </div>

  </InteractivePanel>
{/if}