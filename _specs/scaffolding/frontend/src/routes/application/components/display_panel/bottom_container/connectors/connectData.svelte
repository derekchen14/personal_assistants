<script>
  import HubspotScope from './hubspotScope.svelte';
  import GA4Scope from './ga4Scope.svelte';
  import DriveScope from './driveScope.svelte';
  import GoogleAdsScope from './googleAdsScope.svelte';
  import FacebookScope from './facebookScope.svelte';
  import SalesforceScope from './salesforceScope.svelte';
  import { oauthSuccess, tableView, selectedSpreadsheet, availableSheets } from '@store';
  import { serverUrl, chatActive, displayLayout } from '@store';
  import { displayAlert } from '@alert';
  import { securedFetch } from '$lib/apiUtils';
  import { activeConnector, initializeSheetData, populateSheetData, selectedTable } from '@store';

  let importing = false;
  let performAction = null;
  let buttonConfig = {
    label: 'Import',
    action: 'import',
    color: 'green',
    disabled: true,
    count: null
  };

  function cancelUpload() {
    $displayLayout = 'split';
    $activeConnector = 'upload';
  }

  const catchResourceResponses = async (response) => {
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'An unknown error occurred in the server');
    }
    return response.json();
  };

  const getResources = async (data_source, config) => {
    importing = true; // Show loading spinner
    try {
      const response = await securedFetch(`${serverUrl}/oauth/getResources`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          data_source,
          config
        }),
      });
      const data = await catchResourceResponses(response);

      // Prepare metadata based on data source
      let ssMetadata;
      if (data_source === 'drive' && data.done) {
        ssMetadata = {
          ssName: config.scope.ssName,
          tabNames: data.all_tabs,
        };
      } else if (data_source === 'ga4') {
        ssMetadata = { ssName: 'Google Analytics', tabNames: data.all_tabs };
        tableView.set(data.table);
      } else if (data_source === 'google') {
        ssMetadata = { ssName: 'Google Ads', tabNames: data.all_tabs };
        tableView.set(data.table);
      } else if (data_source === 'hubspot') {
        ssMetadata = { ssName: 'HubSpot', tabNames: data.all_tabs };
        tableView.set(data.table);
      } else if (data_source === 'salesforce') {
        ssMetadata = { ssName: 'Salesforce', tabNames: data.all_tabs };
        tableView.set(data.table);
      } else if (data_source === 'facebook') {
        ssMetadata = { ssName: 'Facebook Ads', tabNames: data.all_tabs };
        tableView.set(data.table);
      }

      initializeSheetData(ssMetadata.tabNames);
      populateSheetData(ssMetadata.tabNames[0], data.table);
      selectedTable.set(ssMetadata.tabNames[0]);

      // Update stores
      selectedSpreadsheet.set(ssMetadata);
      availableSheets.update(currentSheets => [...currentSheets, ssMetadata]);
      $chatActive = true;
      $oauthSuccess = false;
      $displayLayout = 'bottom';
      $activeConnector = null;

      displayAlert('success', `Successfully imported "${ssMetadata.ssName}"`);

    } catch (error) {
      const errorMessage = error.message || 'Failed to get resources';
      displayAlert('error', errorMessage);
      console.error(error);
    } finally {
      importing = false;
    }
  };

  // Component lookup object
  const connectorComponents = {
    'ga4': GA4Scope,
    'google': GoogleAdsScope,
    'hubspot': HubspotScope,
    'salesforce': SalesforceScope,
    'drive': DriveScope,
    'facebook': FacebookScope
  };
</script>

<div class="h-full flex flex-col">
  <div class="flex-1 overflow-hidden">
    {#if $activeConnector && connectorComponents[$activeConnector]}
      <svelte:component 
        this={connectorComponents[$activeConnector]}
        {getResources}
        bind:importing
        bind:performAction
        bind:buttonConfig
      />
    {/if}
  </div>
  
  <!-- Shared Footer -->
  <div class="flex justify-between gap-4 border-t bg-white py-2 px-4">
    <button
      type="button"
      on:click={cancelUpload}
      disabled={importing}
      class="bg-gray-400 text-white rounded-md px-4 py-2 hover:bg-gray-500 disabled:opacity-50">
      Cancel
    </button>
    
    <button 
      type="button"
      on:click={() => performAction && performAction(buttonConfig.action)}
      disabled={importing || buttonConfig.disabled}
      class="text-white rounded-md py-2 px-4 flex items-center gap-2 {buttonConfig.color === 'blue' 
        ? 'bg-blue-500 hover:bg-blue-600 disabled:bg-blue-300' 
        : 'bg-green-500 hover:bg-green-600 disabled:bg-green-300'} disabled:cursor-not-allowed">
      {#if importing}
        <svg class="animate-spin h-4 w-4" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"/>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
        </svg>
      {/if}
      {importing ? 'Importing...' : buttonConfig.label}
      {#if buttonConfig.count !== null}
        ({buttonConfig.count} selected)
      {/if}
    </button>
  </div>
</div>
