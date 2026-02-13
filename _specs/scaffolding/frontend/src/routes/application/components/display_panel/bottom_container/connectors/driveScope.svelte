<script>
  import { onMount } from 'svelte';
  import { activeConnector, oauthSuccess, displayLayout } from '@store';
  import { displayAlert } from '@alert';
  import ConnectorHeader from './components/connectorHeader.svelte';

  // Main props from parent
  export let getResources;
  export let importing = false;
  export let performAction = null;
  export let buttonConfig = {
    label: 'Import',
    action: 'import',
    color: 'green',
    disabled: true,
    count: null
  };

  // Internal state
  export let selectedOption = null;
  let loading = true;
  let files = [];

  $: isImportReady = !!selectedOption;

  let sortField = 'viewedByMeTime';
  let sortDirection = 'desc';

  let showDropdown = false;
  let menuButton;

  let searchQuery = '';
  let filteredFiles = [];

  $: filteredFiles = searchQuery 
    ? files.filter(file => file.name.toLowerCase().includes(searchQuery.toLowerCase()))
    : files;

  $: if (files.length) {
    filteredFiles = searchQuery 
      ? files.filter(file => file.name.toLowerCase().includes(searchQuery.toLowerCase()))
      : files;
    sortFiles();
  }

  function formatDate(dateString) {
    if (!dateString) return 'Never Opened';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  }

  function toggleSort(field) {
    if (sortField === field) {
      sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
      sortField = field;
      sortDirection = 'desc';
    }
    sortFiles();
  }

  function sortFiles() {
    filteredFiles = [...filteredFiles].sort((a, b) => {
      const aValue = a[sortField];
      const bValue = b[sortField];
      
      // Handle missing dates for viewedByMeTime
      if (sortField === 'viewedByMeTime') {
        if (!aValue && !bValue) return 0;
        if (!aValue) return 1;  // Sort missing values to bottom
        if (!bValue) return -1;
      }

      const modifier = sortDirection === 'asc' ? 1 : -1;
      return aValue > bValue ? modifier : -modifier;
    });
  }

  async function loadFiles() {
    loading = true;
    try {
      const response = await fetch('/api/v1/drive/files', {
        credentials: 'include', headers: { 'Accept': 'application/json' }
      });

      if (response.status === 401) {
        // Token expired and refresh failed - trigger reauthorization
        $oauthSuccess = false;
        $activeConnector = 'upload';
        displayAlert('error', 'Please reconnect to Google Drive');
        return;
      }

      if (!response.ok) throw new Error('Failed to load files');
      const data = await response.json();
      files = data.files;
    } catch (error) {
      console.error('Failed to load files:', error);
      displayAlert('error', 'Failed to load Google Drive files');
    } finally {
      loading = false;
    }
  }

  async function disconnectGoogleDrive() {
    try {
      const response = await fetch('/api/v1/disconnectIntegration/drive', {
        method: 'POST', 
        credentials: 'include',
        headers: {'Content-Type': 'application/json' }
      });
      if (response.ok) {
        files = [];
        $oauthSuccess = false;
        $activeConnector = 'upload';
        $displayLayout = 'split';
      } else {
        throw new Error('Disconnect failed');
      }
    } catch (error) {
      console.error(error);
      displayAlert('error', 'Failed to disconnect from Google Drive');
    }
  }

  function handleImport() {
    const metadataPromise = async () => {
      try {
        const metadataResponse = await fetch('/api/v1/drive/files/' + selectedOption.id, {
          headers: {}
        });
        const spreadsheetData = await metadataResponse.json();
        
        const config = {
          scope: {
            id: selectedOption.id,
            ssName: selectedOption.name,
            mimeType: selectedOption.mimeType,
            tabNames: JSON.parse(spreadsheetData).sheets.map(sheet => sheet.properties.title)
          }
        };
        
        getResources('drive', config);
      } catch (error) {
        console.error('Failed to fetch spreadsheet metadata:', error);
        displayAlert('error', 'Failed to get spreadsheet information');
        importing = false;
      }
    };
    
    metadataPromise();
  }

  function handleClickOutside(event) {
    if (menuButton && !menuButton.contains(event.target)) {
      showDropdown = false;
    }
  }

  onMount(() => {
    loadFiles();
    document.addEventListener('click', handleClickOutside);
    
    // Add event listener for import button click
    window.addEventListener('connector-import', handleImport);
    
    return () => {
      document.removeEventListener('click', handleClickOutside);
      window.removeEventListener('connector-import', handleImport);
    }
  });

  // Update button state based on selection
  $: {
    buttonConfig = {
      label: 'Import',
      action: 'import',
      color: 'green',
      disabled: !selectedOption,
      count: null
    };
  }
  
  // Define the performAction function to be called from parent
  performAction = (action) => {
    if (action === 'import') handleImport();
  };
</script>

<div class="flex flex-col h-full overflow-y-auto">
  <!-- Scrollable content area -->
  <ConnectorHeader 
    title="Google Sheets"
    on:refresh={loadFiles}
    on:disconnect={disconnectGoogleDrive}
  >
    <!-- Search input -->
    <div class="relative">
      <input
        type="text"
        placeholder="Search sheets..."
        bind:value={searchQuery}
        class="w-64 px-3 py-1.5 pr-8 text-sm border rounded-md focus:outline-none focus:border-blue-500"
      />
      {#if searchQuery}
        <button
          class="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded-full hover:bg-gray-100"
          on:click={() => searchQuery = ''}
        >
          <svg class="w-4 h-4 text-gray-500" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>
          </svg>
        </button>
      {/if}
    </div>
  </ConnectorHeader>

  <!-- File selection section -->
  <div class="w-full overflow-y-auto">
    {#if loading}
      <div class="flex justify-center items-center">
        <svg class="animate-spin h-8 w-8 text-blue-500" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"/>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
        </svg>
      </div>
    {:else if filteredFiles.length === 0}
      <p class="text-gray-500 text-center">
        {files.length === 0 ? "No spreadsheets found in your Google Drive" : "No matches found"}
      </p>
    {:else}
      <div class="relative">
        <!-- Sticky header -->
        <div class="sticky top-0 bg-white border-b z-10 shadow-sm">
          <div class="grid grid-cols-[1fr,180px,180px] gap-4 p-2 font-semibold text-sm text-gray-600">
            <button 
              class="flex items-center hover:text-gray-900" 
              on:click={() => toggleSort('name')}>
              Name
              {#if sortField === 'name'}
                <span class="ml-1">{sortDirection === 'asc' ? '↑' : '↓'}</span>
              {/if}
            </button>
            <button 
              class="flex items-center hover:text-gray-900" 
              on:click={() => toggleSort('modifiedTime')}>
              Modified
              {#if sortField === 'modifiedTime'}
                <span class="ml-1">{sortDirection === 'asc' ? '↑' : '↓'}</span>
              {/if}
            </button>
            <button 
              class="flex items-center hover:text-gray-900" 
              on:click={() => toggleSort('viewedByMeTime')}>
              Last Opened
              {#if sortField === 'viewedByMeTime'}
                <span class="ml-1">{sortDirection === 'asc' ? '↑' : '↓'}</span>
              {/if}
            </button>
          </div>
        </div>

        <!-- File list -->
        <div class="grid grid-cols-1 gap-1">
          {#each filteredFiles as file}
            <div class="grid grid-cols-[1fr,180px,180px] gap-4 items-center p-2 hover:bg-gray-100 rounded cursor-pointer"
                on:click={() => selectedOption = file}>
              <div class="flex items-center">
                <input type="radio" bind:group={selectedOption} value={file} class="mr-3">
                <span class="truncate">{file.name}</span>
              </div>
              <span class="text-sm text-gray-600">{formatDate(file.modifiedTime)}</span>
              <span class="text-sm text-gray-600">{formatDate(file.viewedByMeTime)}</span>
            </div>
          {/each}
        </div>
      </div>
    {/if}
  </div>
</div>

<style>
  ::-webkit-scrollbar {
    width: 12px;
  }
  ::-webkit-scrollbar-thumb {
    background-color: #707484;
    border-radius: 8px;
  }
  ::-webkit-scrollbar-thumb:hover {
    background-color: #5a5f69;
  }
  ::-webkit-scrollbar-track {
    background-color: #f1f1f1;
    border-radius: 8px;
  }
</style>
