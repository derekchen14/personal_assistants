<script>
  import { Checkbox } from 'flowbite-svelte';
  import { onMount } from 'svelte';
  import { activeConnector, oauthSuccess, displayLayout } from '@store';
  import { displayAlert } from '@alert';
  import DateSelector from './dateSelector.svelte';
  import ConnectorHeader from './components/connectorHeader.svelte';

  // Main props from parent component
  export let getResources;
  export let importing = false;
  export let performAction = null;
  export let buttonConfig = {
    label: 'Continue',
    action: 'continue',
    color: 'blue',
    disabled: true,
    count: 0
  };

  // Internal state
  let selectedCampaigns = [];
  let checkedMetrics = [];
  let selectedStartDate = '';
  let selectedEndDate = '';
  let selectedAccountId = '';
  let currentView = 'selection';
  
  // Update button configuration based on state
  $: {
    if (currentView === 'selection') {
      buttonConfig = {
        label: 'Continue',
        action: 'continue',
        color: 'blue',
        disabled: selectedCampaigns.length === 0,
        count: selectedCampaigns.length
      };
    } else {
      buttonConfig = {
        label: 'Import',
        action: 'import',
        color: 'green',
        disabled: selectedCampaigns.length === 0 || checkedMetrics.length === 0,
        count: null
      };
    }
  }
  
  // Define the actions that can be triggered from parent
  performAction = (action) => {
    if (action === 'import') handleImport();
    if (action === 'continue') continueToConfiguration();
  };

  const metrics = [
    'impressions',
    'clicks', 
    'cpc',
    'ctr',
    'spend',
    'cpm',
    'frequency',
    'reach',
    'cost_per_action_type',
    'actions',
    'return_on_ad_spend',
    'conversions',
    'cost_per_conversion',
    'conversion_rate',
    'landing_page_views',
    'add_to_cart',
    'purchases',
    'revenue'
  ];

  // Function to format display names
  function getDisplayName(field) {
    return field.split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  }

  let loading = true;
  let campaigns = [];
  let metricStates = metrics.map(met => met === 'impressions' || met === 'clicks' || met === 'spend');

  async function loadCampaigns() {
    loading = true;
    try {
      const response = await fetch('/api/v1/facebook/campaigns', {
        credentials: 'include',
        headers: { 
          'Accept': 'application/json',
        }
      });

      if (response.status === 401) {
        // Token expired and refresh failed - trigger reauthorization
        $oauthSuccess = false;
        $activeConnector = 'upload';
        displayAlert('error', 'Please reconnect to Facebook Ads');
        return;
      }

      if (!response.ok) throw new Error('Failed to load campaigns');
      const data = await response.json();
      campaigns = data.campaigns;

      if (campaigns.length > 0 && campaigns[0].id) {
        selectedAccountId = campaigns[0].accountId || '';
      }
    } catch (error) {
      console.error('Failed to load campaigns:', error);
      displayAlert('error', 'Failed to load Facebook Ad campaigns');
    } finally {
      loading = false;
    }
  }

  async function disconnectFacebook() {
    try {
      const response = await fetch('/api/v1/disconnectIntegration/facebook', {
        method: 'POST',
        credentials: 'include',
        headers: { 
          'Content-Type': 'application/json' 
        }
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
      displayAlert('error', 'Failed to disconnect from Facebook Ads');
    }
  }

  function updateCheckedMetrics(index, checked) {
    metricStates[index] = checked;
    checkedMetrics = metrics.filter((met, idx) => metricStates[idx]);
  }

  // Function to handle import action
  function handleImport() {
    // Ensure dates are set
    if (!selectedStartDate || !selectedEndDate) {
      const end = new Date();
      const start = new Date();
      start.setDate(start.getDate() - 30);
      
      selectedStartDate = start.toISOString().split('T')[0];
      selectedEndDate = end.toISOString().split('T')[0];
    }
    
    // Prepare Facebook specific configuration
    console.log("selectedCampaigns", selectedCampaigns);
    console.log("selectedAccountId", selectedAccountId);
    const config = {
      accountId: selectedAccountId,
      campaignIds: selectedCampaigns,
      checkedMetrics,
      dateRange: { 
        startDate: selectedStartDate, 
        endDate: selectedEndDate 
      }
    };
    
    // Call the shared getResources function
    getResources('facebook', config);
  }

  $: isImportReady = currentView === 'selection' ? selectedCampaigns.length > 0 : selectedCampaigns.length > 0 && checkedMetrics.length > 0;
  $: currentCount = selectedCampaigns.length;

  let searchQuery = '';
  let sortField = 'name';
  let sortDirection = 'desc';
  let filteredCampaigns = [];

  $: filteredCampaigns = searchQuery 
    ? campaigns.filter(campaign => campaign.name.toLowerCase().includes(searchQuery.toLowerCase()))
    : campaigns;

  $: if (campaigns.length) {
    filteredCampaigns = searchQuery 
      ? campaigns.filter(campaign => campaign.name.toLowerCase().includes(searchQuery.toLowerCase()))
      : campaigns;
    sortCampaigns();
  }

  function toggleSort(field) {
    if (sortField === field) {
      sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
      sortField = field;
      sortDirection = 'desc';
    }
    sortCampaigns();
  }

  function sortCampaigns() {
    filteredCampaigns = [...filteredCampaigns].sort((a, b) => {
      const aValue = a[sortField];
      const bValue = b[sortField];
      const modifier = sortDirection === 'asc' ? 1 : -1;
      return aValue > bValue ? modifier : -modifier;
    });
  }

  function toggleCampaignSelection(campaign) {
    const index = selectedCampaigns.indexOf(campaign.id);
    if (index === -1) {
      selectedCampaigns = [...selectedCampaigns, campaign.id];
    } else {
      selectedCampaigns = selectedCampaigns.filter(id => id !== campaign.id);
    }
    
    // If this is the first selected campaign, get its account ID
    if (selectedCampaigns.length === 1 && !selectedAccountId) {
      const selectedCampaign = campaigns.find(c => c.id === selectedCampaigns[0]);
      if (selectedCampaign) {
        selectedAccountId = selectedCampaign.accountId;
      }
    }
  }

  function continueToConfiguration() {
    if (selectedCampaigns.length > 0) {
      currentView = 'configuration';
    }
  }

  function goBack() {
    currentView = 'selection';
    // Keep selected campaigns when going back
  }

  onMount(() => {
    loadCampaigns();
    checkedMetrics = metrics.filter((met, idx) => metricStates[idx]);
    
    // Set default date range to last 30 days
    const end = new Date();
    const start = new Date();
    start.setDate(start.getDate() - 30);
    
    selectedStartDate = start.toISOString().split('T')[0];
    selectedEndDate = end.toISOString().split('T')[0];

    // Add event listeners for footer buttons
    window.addEventListener('connector-import', handleImport);
    window.addEventListener('connector-continue', continueToConfiguration);
    
    return () => {
      window.removeEventListener('connector-import', handleImport);
      window.removeEventListener('connector-continue', continueToConfiguration);
    }
  });
</script>

<div class="flex flex-col h-full overflow-y-auto">
  <!-- Scrollable content area -->
  <ConnectorHeader 
    title="Facebook Ads"
    on:refresh={loadCampaigns}
    on:disconnect={disconnectFacebook}
  >
    {#if currentView === 'selection'}
      <!-- Search input -->
      <div class="relative">
        <input
          type="text"
          placeholder="Search campaigns..."
          bind:value={searchQuery}
          class="w-64 px-3 py-1.5 pr-8 text-sm border rounded-md focus:outline-none focus:border-blue-500"
        />
        {#if searchQuery}
          <button
            class="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded-full hover:bg-gray-100"
            on:click={() => searchQuery = ''}
          >
            <svg class="w-4 h-4 text-gray-500" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 1.414 1.414L10 11.414l1.293 1.293a1 1 001.414-1.414L11.414 10l1.293-1.293a1 1 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>
            </svg>
          </button>
        {/if}
      </div>
    {:else}
      <button
        class="flex items-center text-sm text-gray-600 hover:text-gray-900"
        on:click={goBack}
      >
        <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
        </svg>
        Back to Campaigns
      </button>
    {/if}
  </ConnectorHeader>

  {#if currentView === 'selection'}
    <div class="w-full overflow-y-auto">
      {#if loading}
        <div class="flex justify-center items-center py-4">
          <svg class="animate-spin h-8 w-8 text-blue-500" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"/>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
          </svg>
        </div>
      {:else if filteredCampaigns.length === 0}
        <p class="text-gray-500 text-center py-4">
          {campaigns.length === 0 ? "No campaigns found in your Facebook Ads account" : "No matches found"}
        </p>
      {:else}
        <div class="relative">
          <!-- Sticky header -->
          <div class="sticky top-0 bg-white border-b z-10 shadow-sm">
            <div class="grid grid-cols-[auto,1fr,120px] gap-4 p-2 font-semibold text-sm text-gray-600">
              <div class="w-8"></div>
              <button 
                class="flex items-center hover:text-gray-900 text-left" 
                on:click={() => toggleSort('name')}>
                Campaign Name
                {#if sortField === 'name'}
                  <span class="ml-1">{sortDirection === 'asc' ? '↑' : '↓'}</span>
                {/if}
              </button>
              <button 
                class="flex items-center hover:text-gray-900" 
                on:click={() => toggleSort('status')}>
                Status
                {#if sortField === 'status'}
                  <span class="ml-1">{sortDirection === 'asc' ? '↑' : '↓'}</span>
                {/if}
              </button>
            </div>
          </div>

          <!-- Campaign list -->
          <div class="grid grid-cols-1 gap-1">
            {#each filteredCampaigns as campaign}
              <div 
                class="grid grid-cols-[auto,1fr,120px] gap-4 items-center p-2 hover:bg-gray-100 rounded cursor-pointer"
                on:click={() => toggleCampaignSelection(campaign)}
              >
                <div class="flex justify-center items-center">
                  <Checkbox
                    checked={selectedCampaigns.includes(campaign.id)}
                    on:change={() => toggleCampaignSelection(campaign)}
                    on:click={(e) => e.stopPropagation()}
                  />
                </div>
                <div class="truncate">{campaign.name}</div>
                <div class="text-sm text-gray-600">{campaign.status}</div>
              </div>
            {/each}
          </div>
        </div>
      {/if}
    </div>
  {:else}
    <div class="py-3">
      <!-- Campaign selection summary -->
      <div class="px-4 mb-6">
        <h3 class="text-xl font-medium text-gray-900 mb-1">Selected Campaigns: {selectedCampaigns.length}</h3>
        <div class="text-sm text-gray-500">
          Account ID: {selectedAccountId}
        </div>
      </div>

      <hr class="h-px my-4 bg-gray-200 border-0">

      <!-- Date Selection -->
      <DateSelector 
        bind:selectedStartDate={selectedStartDate} 
        bind:selectedEndDate={selectedEndDate} 
        showQuickSelect={true}
      />

      <hr class="h-px my-4 bg-gray-200 border-0">

      <!-- Metrics Selection -->
      <div class="px-4 mt-6">
        <h4 class="text-sm font-medium text-gray-700 mb-2">Select Metrics:</h4>
        <div class="grid grid-cols-2 gap-x-6">
          {#each metrics as met, index}
            <div class="mb-2.5">
              <Checkbox
                bind:checked={metricStates[index]}
                on:change={() => updateCheckedMetrics(index, metricStates[index])}
              >{getDisplayName(met)}</Checkbox>
            </div>
          {/each}
        </div>
      </div>
    </div>
  {/if}
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
