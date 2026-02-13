<script>
  import { writable, get } from 'svelte/store';
  import { onMount } from 'svelte';
  import { securedFetch } from '$lib/apiUtils';
  import { displayAlert } from '@alert';
  import { serverUrl, tableView, chatActive, displayLayout, activeConnector, availableSheets, fileSelectorView } from '@store';
  import { initializeSocket, initializeSheetData, updateTabProperties, selectedSpreadsheet, selectedTable } from '@store';
  import InteractivePanel from './stages/components/interactiveComp.svelte';

  export const selectedSources = writable(new Set());
  let sources = [];
  let loading = true;
  let isLoading = false;

  onMount(async () => {
    try {
      const response = await securedFetch(`${serverUrl}/sheets/user-sources`);
      if (response.ok) {
        const data = await response.json();
        sources = data.sources;
      }
    } catch (error) {
      console.error('Failed to fetch user sources:', error);
    } finally {
      loading = false;
    }
  });

  function formatSize(kb) {
    if (kb < 1024) return `${kb} KB`;
    return `${(kb / 1024).toFixed(1)} MB`;
  }

  function formatDate(dateStr) {
    return new Date(dateStr).toLocaleDateString();
  }

  function toggleSource(id) {
    selectedSources.update(s => {
      const newSet = new Set(s);
      if (newSet.has(id)) {
        newSet.delete(id);
      } else {
        newSet.add(id);
      }
      return newSet;
    });
  }

  const handleCancel = () => {
    selectedSources.set(new Set());
    $fileSelectorView = false;
    $displayLayout = 'split';
  }

  function resetState() {
    chatActive.set(false);
    tableView.set(null);
    isLoading = true;
  }

  async function handleLoad() {
    try {
      resetState();

      const formData = new FormData();
      formData.append('source_ids', JSON.stringify(Array.from($selectedSources)));

      const response = await securedFetch(`${serverUrl}/sheets/load-source`, {
        method: 'POST',
        body: formData
      });

      if (response.ok) {
        const data = await response.json();

        if (data.table && data.table.length > 0) {
          const ssName = "Data Source";
          const tabNames = Object.keys(data.properties || {});

          if (tabNames.length === 0) {
            displayAlert('warning', 'No tables found in selected data sources.');
            isLoading = false;
            return;
          }

          const spreadsheet = { ssName, tabNames };

          const socketConnection = await initializeSocket();
          if (socketConnection) {
            selectedSpreadsheet.set(spreadsheet);
            $activeConnector = null;
            $displayLayout = 'bottom';
            initializeSheetData(tabNames);

            if (data.properties) {
              Object.entries(data.properties).forEach(([tabName, schema]) => {
                updateTabProperties(tabName, schema);
              });
            }

            availableSheets.update((currentSheets) => [...currentSheets, spreadsheet]);
            selectedTable.set(tabNames[0]);
            tableView.set(data.table);
            chatActive.set(true);

            isLoading = false;
            displayAlert('success', 'Successfully loaded selected data sources');
            $fileSelectorView = false;
          } else {
            isLoading = false;
            displayAlert('error', 'Failed to load data sources due to socket connection issue.');
          }
        } else {
          isLoading = false;
          displayAlert('warning', 'No tables found in selected data sources.');
        }
      } else {
        isLoading = false;
        const error = await response.json();
        throw new Error(error.detail);
      }
    } catch (error) {
      isLoading = false;
      displayAlert('error', `Failed to load data sources: ${error.message}`);
    }
  }

  async function handleDelete(sourceId) {
    try {
      const response = await securedFetch(`${serverUrl}/sheets/user-sources/${sourceId}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        sources = sources.filter(s => s.id !== sourceId);
        displayAlert('success', 'Data source deleted successfully');
      } else {
        const error = await response.json();
        throw new Error(error.detail);
      }
    } catch (error) {
      displayAlert('error', `Failed to delete data source: ${error.message}`);
    }
  }
</script>

<InteractivePanel title="Your Files" subtitle="Select files to load into the chat:"
  onReject={handleCancel} rejectLabel="Cancel"
  onAccept={handleLoad} acceptLabel={isLoading ? 'Loading...' : 'Load Selected'}>

  {#if loading}
    <div class="animate-pulse">
      <div class="h-4 bg-gray-200 rounded w-3/4 mb-4"></div>
      <div class="h-4 bg-gray-200 rounded w-1/2"></div>
    </div>
  {:else}
    <div class="space-y-2 w-full">
      {#if sources.length === 0}
        <p class="my-1 text-lg">No uploaded files yet</p>
      {:else}
        <div class="space-y-0 w-full">
          {#each sources as source}
            <label class="group flex items-center space-x-3 p-3 rounded-lg hover:bg-gray-50 cursor-pointer w-full">
              <input
                type="checkbox"
                checked={$selectedSources.has(source.id)}
                on:change={() => toggleSource(source.id)}
                class="h-4 w-4 text-teal-600 focus:ring-teal-500 border-gray-300 rounded"
              />
              <div class="flex-1 w-full">
                <div class="flex justify-between">
                  <span class="font-medium">{source.name}</span>
                  <div class="flex items-center space-x-2">
                    <span class="text-sm text-gray-500 group-hover:hidden">{formatSize(source.size_kb)}</span>
                    <button 
                      class="hidden group-hover:block text-gray-500 hover:text-red-600 transition-colors"
                      on:click|stopPropagation={() => handleDelete(source.id)}
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                        <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd" />
                      </svg>
                    </button>
                  </div>
                </div>
                <div class="flex justify-between text-sm text-gray-500">
                  <span>{source.provider}</span>
                  <span>{formatDate(source.created_at)}</span>
                </div>
              </div>
            </label>
          {/each}
        </div>
      {/if}
    </div>
  {/if}
</InteractivePanel>