<script lang="ts">
  import DialoguePanel from './components/dialogue_panel/dialoguePanel.svelte';
  import DisplayPanel from './components/display_panel/displayPanel.svelte';
  import { onMount, onDestroy } from 'svelte';
  import { showResetModal, resetChat, initializeSocket } from '@store';
  import ResetModal from './lib/resetModal.svelte';
  import { goto } from '$app/navigation';
  import { checkAuthentication } from '$lib/apiUtils';
  import { clearAlert } from '@alert';
  import { page } from '$app/stores';
  import { securedFetch } from '$lib/apiUtils';
  import { serverUrl } from '@store';
  import { 
    chatActive, 
    displayLayout, 
    activeConnector, 
    availableSheets, 
    tableView,
    selectedSpreadsheet,
    selectedTable,
    initializeSheetData,
    updateTabProperties,
    populateSheetData
  } from '@store';

  let isNavigating = false;
  let browserWindow = null;
  let isLoading = true;
  
  onMount(async () => {
    try {
      const isAuthenticated = await checkAuthentication();
      
      if (!isAuthenticated) {
        if (!isNavigating) {
          isNavigating = true;
          goto('/login');
        }
        return;
      }

      // Check if we're in a conversation route
      const conversationMatch = $page.url.pathname.match(/\/conversation\/([^/]+)/);
      
      if (conversationMatch) {
        const conversationId = conversationMatch[1];
        console.log('Loading conversation:', conversationId);
        
        const conversationResponse = await securedFetch(`${serverUrl}/conversation/${conversationId}`);
        
        if (conversationResponse.ok) {
          const conversationData = await conversationResponse.json();
          console.log('Received conversation data:', conversationData);
          
          // Reset state
          chatActive.set(false);
          tableView.set(null);
          availableSheets.set([]);

          // Initialize socket connection first
          console.log('Initializing socket connection...');
          try {
            const socketConnection = await initializeSocket();
            console.log('Socket connection established');
          } catch (error) {
            console.error('Socket connection failed:', error);
            throw new Error('Failed to establish socket connection');
          }

          // Accumulate all tabs, properties, and tables
          let allTabNames = [];
          let allProperties = {};
          let allTables = {};
          let allSheets = [];

          for (const source of conversationData.data_sources) {
            const tabNames = [source.name]; // Each source is a table
            allTabNames.push(...tabNames);
            
            if (source.properties) {
              Object.assign(allProperties, { [source.name]: source.properties });
            }
            
            if (source.content) {
              allTables[source.name] = source.content;
            }

            const spreadsheet = { 
              ssName: source.name, 
              tabNames: [source.name] 
            };
            allSheets.push(spreadsheet);
          }

          // After loop, set up stores for all spreadsheets
          if (allSheets.length > 0) {
            availableSheets.set(allSheets);
            selectedSpreadsheet.set({
              ssName: allSheets.map(sheet => sheet.ssName).join(', '),
              tabNames: allTabNames
            });
            $activeConnector = null;
            $displayLayout = 'bottom';

            // Initialize all tabs for all sheets
            allSheets.forEach(sheet => {
              initializeSheetData(sheet.tabNames);
              sheet.tabNames.forEach(tabName => {
                if (allProperties[tabName]) {
                  updateTabProperties(tabName, allProperties[tabName]);
                }
                if (allTables[tabName]) {
                  populateSheetData(tabName, allTables[tabName]);
                }
              });
            });

            selectedTable.set(allSheets[0].tabNames[0]);
            tableView.set(allTables[allSheets[0].tabNames[0]]);
          } else {
            console.warn('No sheets to load');
          }

          // Activate chat after all data sources are loaded
          chatActive.set(true);
        } else {
          console.error('Failed to load conversation:', await conversationResponse.text());
          // If conversation not found, redirect to main application page
          goto('/application');
        }
      } else {
        const socket = await initializeSocket();
        if (!socket) {
          throw new Error('Failed to establish socket connection');
        }
      }
      
      browserWindow = window;
      browserWindow.history.pushState(null, null, browserWindow.location.href);
      browserWindow.onpopstate = function () {
        browserWindow.history.go(1);
      };
      clearAlert();
      isLoading = false;
    } catch (error) {
      console.error('Error in layout mount:', error);
      isLoading = false; // Make sure to set loading to false even on error
      if (!isNavigating) {
        isNavigating = true;
        goto('/login');
      }
    }
  });

  onDestroy(() => {
    if (browserWindow) {
      browserWindow.onpopstate = null;
    }
  });
</script>

<svelte:head>
  <title>Soleda: Dana</title>
</svelte:head>

{#if isLoading}
  <div class="fixed inset-0 flex items-center justify-center">
    <div class="animate-spin rounded-full h-32 w-32 border-t-2 border-b-2 border-blue-500"></div>
  </div>
{:else}
  <div class="flex flex-col flex-grow md:flex-row h-full max-w-screen w-screen p-3 gap-4">
    <DialoguePanel />
    <DisplayPanel />
    <slot />
  </div>

  {#if $showResetModal}
    <ResetModal message="Do you want to clear out the existing conversation to start a new session?"
        onConfirm={resetChat} onCancel={() => showResetModal.set(false)} />
  {/if}
{/if} 