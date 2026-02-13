<script>
  import { Checkbox } from 'flowbite-svelte';
  import { onMount } from 'svelte';
  import { activeConnector, oauthSuccess, displayLayout } from '@store';
  import { displayAlert } from '@alert';
  import DateSelector from './dateSelector.svelte';
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
  let checkedDimensions = [];
  let checkedMetrics = [];
  let selectedProperty = null;
  let selectedStartDate = '';
  let selectedEndDate = '';

  const dimensions = [
    'Ad format',
    'Ad source',
    'Ad unit',
    'Audience name',
    'Interests',
    'Browser',
    'Campaign ID',
    'Campaign',
    'City',
    'Country',
    'Date',
    'Date + hour (YYYYMMDDHH)',
    'Day of week',
    'Default channel group',
    'Device category',
    'Event name',
    'Google Ads account name',
    'Google Ads ad group name',
    'Google Ads campaign',
    'Landing page',
    'Language',
    'Medium',
    'Operating system',
    'Platform',
    'Region',
    'Search term',
    'Session campaign',
    'Device brand',
    'New / returning',
    'Operating system with version',
    'Page location',
    'Page title',
  ];

  const metrics = [
    '1-day active users',
    '28-day active users',
    '7-day active users',
    'Active users',
    'Ad unit exposure',
    'Add to carts',
    'Ads clicks',
    'Ads cost',
    'Ads cost per click',
    'Cost per conversion',
    'Ads impressions',
    'Average purchase revenue',
    'ARPPU',
    'Average purchase revenue per user',
    'ARPU',
    'Average session duration',
    'Bounce rate',
    'Cart-to-view rate',
    'Checkouts',
    'Cohort active users',
    'Cohort total users',
    'Conversions',
    'Crash-affected users',
    'Crash-free users rate',
    'DAU / MAU',
    'DAU / WAU',
    'Ecommerce purchases',
    'Engaged sessions',
    'Engagement rate',
    'Event count',
    'Event count per user',
    'Event value',
    'Total revenue',
  ];

  let loading = true;
  let properties = [];

  // Update button configuration based on component state
  $: {
    buttonConfig = {
      label: 'Import',
      action: 'import',
      color: 'green',
      disabled: !selectedProperty || checkedMetrics.length === 0,
      count: null
    };
  }

  // Define the performAction function to be called from parent
  performAction = (action) => {
    if (action === 'import') handleImport();
  };

  async function loadProperties() {
    loading = true;
    try {
      const response = await fetch('/api/v1/ga4/properties', {
        credentials: 'include', headers: { 'Accept': 'application/json' }
      });

      if (response.status === 401) {
        // Token expired and refresh failed - trigger reauthorization
        $oauthSuccess = false;
        $activeConnector = 'upload';
        displayAlert('error', 'Please reconnect to Google Analytics');
        return;
      }

      if (!response.ok) throw new Error('Failed to load properties');
      const data = await response.json();
      properties = data.properties;
      
      if (properties.length > 0 && !selectedProperty) {
        selectedProperty = properties[0].propertyId;
      }
    } catch (error) {
      console.error('Failed to load files:', error);
      displayAlert('error', 'Failed to load Google Analytics properties');
    } finally {
      loading = false;
    }
  }

  let dimensionStates = dimensions.map(
    (dim) => dim === 'Browser' || dim === 'Country' || dim === 'Date',
  );
  let metricStates = metrics.map((met) => met === 'Total revenue' || met === 'Active users');

  function updateCheckedDimensions(index, checked) {
    dimensionStates[index] = checked;
    checkedDimensions = dimensions.filter((dim, idx) => dimensionStates[idx]);
  }

  function updateCheckedMetrics(index, checked) {
    metricStates[index] = checked;
    checkedMetrics = metrics.filter((met, idx) => metricStates[idx]);
  }

  async function disconnectGA() {
    try {
      const response = await fetch('/api/v1/disconnectIntegration/ga4', {
        method: 'POST',
        credentials: 'include',
        headers: {'Content-Type': 'application/json' }
      });
      if (response.ok) {
        $oauthSuccess = false;
        $activeConnector = 'upload';
        $displayLayout = 'split';
      } else {
        throw new Error('Disconnect failed');
      }
    } catch (error) {
      console.error(error);
      displayAlert('error', 'Failed to disconnect from Google Analytics');
    }
  }
  
  function handleImport() {
    // Prepare GA4 specific configuration
    const config = {
      dimensions: checkedDimensions,
      metrics: checkedMetrics,
      propertyId: selectedProperty,
      dateRange: { startDate: selectedStartDate, endDate: selectedEndDate }
    };
    
    // Call the shared getResources function
    getResources('ga4', config);
  }

  onMount(() => {
    loadProperties();
    checkedDimensions = dimensions.filter((dim, idx) => dimensionStates[idx]);
    checkedMetrics = metrics.filter((met, idx) => metricStates[idx]);

    // Set default date range if not already set
    if (!selectedStartDate || !selectedEndDate) {
      const end = new Date();
      const start = new Date();
      start.setDate(start.getDate() - 30);
      
      selectedStartDate = start.toISOString().split('T')[0];
      selectedEndDate = end.toISOString().split('T')[0];
    }
  });
</script>

<div class="flex flex-col h-full overflow-y-auto">
  <!-- Scrollable content area -->
  <ConnectorHeader 
    title="Google Analytics"
    on:refresh={loadProperties}
    on:disconnect={disconnectGA}
  />

  <!-- Property Selection -->
  <div class="px-4 mb-4">
    <h4 class="text-sm font-medium text-gray-700 mb-2">Select Property:</h4>
    {#if loading}
      <div class="flex justify-center items-center py-4">
        <svg class="animate-spin h-8 w-8 text-blue-500" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"/>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
        </svg>
      </div>
    {:else if properties.length === 0}
      <p class="text-gray-500 text-center py-4">No properties found in your Google Analytics account</p>
    {:else}
      <div class="grid grid-cols-2 gap-3">
        {#each properties as property}
          <label class="relative flex items-start p-3 cursor-pointer border rounded-lg 
                      hover:border-blue-500 transition-colors
                      {selectedProperty === property.propertyId ? 'border-blue-500 bg-blue-50' : 'border-gray-200'}">
            <input
              type="radio"
              name="property"
              value={property.propertyId}
              bind:group={selectedProperty}
              class="absolute opacity-0"
            />
            <div>
              <div class="font-medium">{property.displayName}</div>
              <div class="text-xs text-gray-500">ID: {property.propertyId}</div>
            </div>
          </label>
        {/each}
      </div>
    {/if}
  </div>

  <!-- Update the DateSelector binding -->
  <DateSelector 
    bind:selectedStartDate={selectedStartDate} 
    bind:selectedEndDate={selectedEndDate} 
    showQuickSelect={true} 
  />

  <!-- Replace the step-based UI with a two-column layout -->
  <div class="px-4">
    <h4 class="text-sm font-medium text-gray-700 mb-2">Select Metrics and Dimensions:</h4>
    <div class="grid grid-cols-2 gap-6">
      <!-- Dimensions Column -->
      <div>
        <h5 class="text-md font-medium text-gray-600 mb-2">Dimensions</h5>
        {#each dimensions as dim, index}
          <div class="mb-2.5">
            <Checkbox
              bind:checked={dimensionStates[index]}
              on:change={() => updateCheckedDimensions(index, dimensionStates[index])}
            >{dim}</Checkbox>
          </div>
        {/each}
      </div>

      <!-- Metrics Column -->
      <div>
        <h5 class="text-md font-medium text-gray-600 mb-2">Metrics</h5>
        {#each metrics as met, index}
          <div class="mb-2.5">
            <Checkbox
              bind:checked={metricStates[index]}
              on:change={() => updateCheckedMetrics(index, metricStates[index])}
            >{met}</Checkbox>
          </div>
        {/each}
      </div>
    </div>
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
