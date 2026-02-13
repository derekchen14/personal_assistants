<script>
  import { Checkbox, Radio, Tooltip } from 'flowbite-svelte';
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
    label: 'Continue',
    action: 'continue',
    color: 'blue',
    disabled: true,
    count: 0
  };

  // Internal state
  let selectedCampaigns = [];
  let selectedAccountId = '';
  let selectedStartDate = '';
  let selectedEndDate = '';
  let selectedFields = [];

  let currentView = 'selection';
  let searchQuery = '';
  let sortField = 'name';
  let sortDirection = 'desc';
  let campaigns = [];
  let loading = false;
  let filteredCampaigns = [];

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
        disabled: selectedCampaigns.length === 0 || selectedFields.length === 0,
        count: null
      };
    }
  }

  // Define the actions that can be triggered from parent
  performAction = (action) => {
    if (action === 'import') handleImport();
    if (action === 'continue') continueToConfiguration();
  };

  const today = new Date();
  const thirtyDaysAgo = new Date();
  thirtyDaysAgo.setDate(today.getDate() - 30);

  const coreDateSegments = ['segments.date', 'segments.week', 'segments.month', 'segments.quarter', 'segments.year'];
  const otherSegments = ['segments.device', 'segments.hour', 'segments.day_of_week', 'segments.ad_network_type'];
  const dimensionFields = ['campaign.id', 'campaign.name', 'campaign.status', 'campaign.advertising_channel_type', 
      'campaign.serving_status', 'campaign.bidding_strategy_type'];

  const primaryMetrics = ['metrics.impressions', 'metrics.clicks', 'metrics.ctr', 'metrics.cost_micros', 
      'metrics.average_cpc', 'metrics.conversions', 'metrics.conversions_from_interactions_rate'];

  const secondaryMetrics = ['metrics.average_cpm', 'metrics.cost_per_conversion', 'metrics.conversions_value', 
      'metrics.value_per_conversion', 'metrics.all_conversions', 'metrics.all_conversions_value', 
      'metrics.engagements', 'metrics.engagement_rate', 'metrics.interactions', 'metrics.interaction_rate', 
      'metrics.video_views', 'metrics.video_view_rate', 'metrics.active_view_impressions', 
      'metrics.active_view_measurable_impressions', 'metrics.active_view_measurability', 
      'metrics.active_view_viewability', 'metrics.active_view_ctr', 'metrics.active_view_cpm', 
      'metrics.search_impression_share', 'metrics.search_budget_lost_impression_share', 
      'metrics.search_rank_lost_impression_share'];

  const tertiaryMetrics = ['metrics.average_cost', 'metrics.top_impression_percentage', 
      'metrics.absolute_top_impression_percentage', 'metrics.search_exact_match_impression_share', 
      'metrics.search_top_impression_share', 'metrics.search_absolute_top_impression_share', 
      'metrics.phone_calls', 'metrics.phone_impressions', 'metrics.phone_through_rate'];

  const hourIncompatibleMetrics = ['metrics.phone_impressions', 'metrics.phone_through_rate', 'metrics.phone_calls'];
  const deviceIncompatibleMetrics = [];

  const allMetrics = [...primaryMetrics, ...secondaryMetrics, ...tertiaryMetrics];
  const availableFields = [...coreDateSegments, ...otherSegments, ...dimensionFields, ...allMetrics];

  const formatDate = (date) => date.toISOString().split('T')[0];
  
  let selectedSegments = [];

  // Initialize fieldStates to check primary metrics by default
  let fieldStates = availableFields.map(field => primaryMetrics.includes(field));

  // Metric category visibility
  let showCommonMetrics = true;
  let showSecondaryMetrics = false;
  let showTertiaryMetrics = false;

  // Format display names
  function getDisplayName(field) {
      return field.split('.').pop().split('_')
          .map(word => word.charAt(0).toUpperCase() + word.slice(1))
          .join(' ');
  }

  let selectedTimePeriod = 'none';
  let selectedAggregation = 'none';

  // Update dateSegmentGroups to include display names
  const dateSegmentGroups = {
      'Time Period': {
          none: 'No time breakdown',
          options: [
              { value: 'segments.date', display: 'Date' },
              { value: 'segments.week', display: 'Week' },
              { value: 'segments.month', display: 'Month' }
          ]
      },
      'Aggregation': {
          none: 'No aggregation',
          options: [
              { value: 'segments.quarter', display: 'Quarter' },
              { value: 'segments.year', display: 'Year' }
          ]
      }
  };

  async function loadCampaigns() {
    loading = true;
    try {
      const response = await fetch('/api/v1/google/campaigns', {
        credentials: 'include',
        headers: { 
          'Accept': 'application/json'
        }
      });

      if (!response.ok) throw new Error('Failed to load campaigns');
      const data = await response.json();
      campaigns = data.campaigns;
      filteredCampaigns = campaigns;
    } catch (error) {
      console.error('Failed to load campaigns:', error);
      displayAlert('error', 'Failed to load Google Ads campaigns');
    } finally {
      loading = false;
    }
  }

  function toggleCampaignSelection(campaign) {
    const index = selectedCampaigns.indexOf(campaign.id);
    if (index === -1) {
      selectedCampaigns = [...selectedCampaigns, campaign.id];
    } else {
      selectedCampaigns = selectedCampaigns.filter(id => id !== campaign.id);
    }
    
    // Set account ID from first selected campaign
    if (selectedCampaigns.length === 1 && !selectedAccountId) {
      const selectedCampaign = campaigns.find(c => c.id === selectedCampaigns[0]);
      if (selectedCampaign) {
        selectedAccountId = selectedCampaign.accountId;
      }
    }
  }

  function handleImport() {
    // Ensure dates are set
    if (!selectedStartDate || !selectedEndDate) {
      const end = new Date();
      const start = new Date();
      start.setDate(start.getDate() - 30);
      
      selectedStartDate = start.toISOString().split('T')[0];
      selectedEndDate = end.toISOString().split('T')[0];
    }

    const config = {
      accountId: selectedAccountId,
      campaignIds: selectedCampaigns,
      selectedFields,
      dateRange: {
        startDate: selectedStartDate,
        endDate: selectedEndDate
      }
    };
    
    getResources('google', config);
  }

  function continueToConfiguration() {
    if (selectedCampaigns.length > 0) {
      currentView = 'configuration';
    }
  }

  function goBack() {
    currentView = 'selection';
  }

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

  onMount(() => {
    loadCampaigns();
    
    // Initialize selectedFields with required fields and common metrics
    selectedFields = [
      ...dimensionFields.slice(0, 2), // campaign.id and campaign.name
      ...primaryMetrics.slice(0, 3)   // impressions, clicks, and ctr
    ];

    // Set corresponding fieldStates to true for default selections
    selectedFields.forEach(field => {
      const index = availableFields.indexOf(field);
      if (index !== -1) {
        fieldStates[index] = true;
      }
    });
    
    // Set default date range
    const end = new Date();
    const start = new Date();
    start.setDate(start.getDate() - 30);
    
    selectedStartDate = start.toISOString().split('T')[0];
    selectedEndDate = end.toISOString().split('T')[0];
  });

  function validateFieldSelection(field, checked) {
    // Handle hour segment incompatibilities
    if (field === 'segments.hour' && checked) {
      hourIncompatibleMetrics.forEach(metric => {
        const idx = availableFields.indexOf(metric);
        fieldStates[idx] = false;
      });
    }

    // Handle device segment incompatibilities
    if (field === 'segments.device' && checked) {
      deviceIncompatibleMetrics.forEach(metric => {
        const idx = availableFields.indexOf(metric);
        fieldStates[idx] = false;
      });
    }

    // Prevent selecting incompatible metrics when segments are active
    if (checked) {
      if (fieldStates[availableFields.indexOf('segments.hour')] && hourIncompatibleMetrics.includes(field)) {
        return false;
      }
      if (fieldStates[availableFields.indexOf('segments.device')] && deviceIncompatibleMetrics.includes(field)) {
        return false;
      }
    }

    return true;
  }

  function updateSelectedFields(index, checked) {
      const field = availableFields[index];
      
      // Handle radio selections automatically through binding
      // Only handle non-date segments here
      if (!Object.values(dateSegmentGroups).flat().includes(field)) {
          if (!validateFieldSelection(field, checked)) {
              fieldStates[index] = false;
              return;
          }

          fieldStates[index] = checked;
      }
      
      // Combine required fields with selected fields and selected date segments
      selectedFields = [
          ...(selectedTimePeriod !== 'none' ? [selectedTimePeriod] : []),
          ...(selectedAggregation !== 'none' ? [selectedAggregation] : []),
          ...availableFields.filter((field, idx) => fieldStates[idx])
      ];

      // Update segments tracking for non-date segments
      if (otherSegments.includes(field)) {
          if (checked) {
              selectedSegments.push(field);
          } else {
              selectedSegments = selectedSegments.filter(f => f !== field);
          }
          selectedSegments = [...selectedSegments];
      }
  }

  $: metricFields = [
    ...primaryMetrics,
    ...secondaryMetrics,
    ...tertiaryMetrics
  ].filter(m => {
    if (fieldStates[availableFields.indexOf('segments.hour')] && hourIncompatibleMetrics.includes(m)) {
      return false;
    }
    if (fieldStates[availableFields.indexOf('segments.device')] && deviceIncompatibleMetrics.includes(m)) {
      return false;
    }
    return true;
  });

  async function disconnectGoogleAds() {
    try {
      const response = await fetch('/api/v1/disconnectIntegration/google', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' }
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
      displayAlert('error', 'Failed to disconnect from Google Ads');
    }
  }

  // Get metric incompatibility message
  function getIncompatibilityMessage(field) {
      if (hourIncompatibleMetrics.includes(field) && fieldStates[availableFields.indexOf('segments.hour')]) {
          return "Cannot be selected when Hour segmentation is active";
      }
      return null;
  }

  // Check if field should be disabled
  function isFieldDisabled(field) {
      if (field === 'segments.hour') {
          return hourIncompatibleMetrics.some(metric => 
              fieldStates[availableFields.indexOf(metric)] === true
          );
      }
      return hourIncompatibleMetrics.includes(field) && 
             fieldStates[availableFields.indexOf('segments.hour')];
  }

  // Handle checkbox states
  $: checkboxStates = availableFields.map(field => {
      const isDisabled = isFieldDisabled(field);
      let tooltipMessage = null;

      if (field === 'segments.hour' && isDisabled) {
          tooltipMessage = getSegmentIncompatibilityMessage('segments.hour');
      } else if (hourIncompatibleMetrics.includes(field) && fieldStates[availableFields.indexOf('segments.hour')]) {
          tooltipMessage = "Cannot be used with Hour segmentation";
      }

      return {
          disabled: isDisabled,
          tooltip: tooltipMessage
      };
  });

  // Simplify and fix the segment disabling logic
  function isSegmentDisabled(segment) {
      if (segment === 'segments.hour') {
          // Check if ANY phone-related metrics are selected
          return hourIncompatibleMetrics.some(metric => 
              fieldStates[availableFields.indexOf(metric)] === true
          );
      }
      return false;
  }

  function getSegmentIncompatibilityMessage(segment) {
      if (segment === 'segments.hour') {
          const selectedIncompatibles = hourIncompatibleMetrics
              .filter(m => fieldStates[availableFields.indexOf(m)] === true)
              .map(m => getDisplayName(m));
          
          if (selectedIncompatibles.length > 0) {
              return `Cannot be used with: ${selectedIncompatibles.join(', ')}`;
          }
      }
      return null;
  }

  // Ensure Hour gets disabled when incompatible metrics are selected
  $: {
      const hourIndex = availableFields.indexOf('segments.hour');
      const hasIncompatibleMetrics = hourIncompatibleMetrics.some(
          metric => fieldStates[availableFields.indexOf(metric)] === true
      );

      if (hasIncompatibleMetrics && fieldStates[hourIndex]) {
          // Force uncheck hour if incompatible metrics are selected
          fieldStates[hourIndex] = false;
      }
  }

  // Update the checkbox states reactively to handle both metrics and segments consistently
  $: checkboxStates = availableFields.map(field => {
      const isHourSegment = field === 'segments.hour';
      const hasIncompatibleMetrics = hourIncompatibleMetrics.some(
          metric => fieldStates[availableFields.indexOf(metric)] === true
      );

      if (isHourSegment) {
          return {
              disabled: hasIncompatibleMetrics,
              tooltip: hasIncompatibleMetrics ? getSegmentIncompatibilityMessage('segments.hour') : null
          };
      }

      const isHourMetric = hourIncompatibleMetrics.includes(field);
      const hourActive = fieldStates[availableFields.indexOf('segments.hour')];

      return {
          disabled: isHourMetric && hourActive,
          tooltip: isHourMetric && hourActive ? "Cannot be used with Hour segmentation" : null
      };
  });

</script>

<!-- Campaign selection view -->
{#if currentView === 'selection'}
  <div class="flex flex-col h-full overflow-y-auto">
    <ConnectorHeader 
      title="Google Ads"
      on:refresh={loadCampaigns}
      on:disconnect={disconnectGoogleAds}
    >
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
    </ConnectorHeader>

    <!-- Campaign list section -->
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
          {campaigns.length === 0 ? "No campaigns found in your Google Ads account" : "No matches found"}
        </p>
      {:else}
        <!-- Campaign list header -->
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
      {/if}
    </div>
  </div>

<!-- Configuration view -->
{:else}
  <div class="flex flex-col h-full overflow-y-auto">
    <ConnectorHeader 
      title="Google Ads"
      on:refresh={loadCampaigns}
      on:disconnect={disconnectGoogleAds}
    >
      <button
        class="flex items-center text-sm text-gray-600 hover:text-gray-900"
        on:click={goBack}
      >
        <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
        </svg>
        Back to Campaigns
      </button>
    </ConnectorHeader>

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

      <!-- Fields Selection -->
      <div class="px-4">
          <div class="grid grid-cols-3 gap-6">
              <!-- Segments section -->
              <div>
                  <h5 class="text-sm font-medium text-gray-600 mb-2">Segments</h5>
                  <div class="mb-4">
                      {#each Object.entries(dateSegmentGroups) as [groupName, group]}
                          <div class="mb-3">
                              <div class="text-xs text-gray-400 mb-1">{groupName}</div>
                              <div class="mb-0">
                                  <Radio
                                      value="none"
                                      group={groupName === 'Time Period' ? selectedTimePeriod : selectedAggregation}
                                      class="hover:bg-gray-200 rounded-md transition-colors p-1 -ml-1"
                                      on:change={() => {
                                          if (groupName === 'Time Period') {
                                              selectedTimePeriod = 'none';
                                          } else {
                                              selectedAggregation = 'none';
                                          }
                                          updateSelectedFields(-1, true);
                                      }}
                                  >{group.none}</Radio>
                              </div>
                              {#each group.options as option}
                                  <div class="mb-0">
                                      <Radio
                                          value={option.value}
                                          class="hover:bg-gray-200 rounded-md transition-colors p-1 -ml-1"
                                          group={groupName === 'Time Period' ? selectedTimePeriod : selectedAggregation}
                                          on:change={() => {
                                              if (groupName === 'Time Period') {
                                                  selectedTimePeriod = option.value;
                                              } else {
                                                  selectedAggregation = option.value;
                                              }
                                              updateSelectedFields(-1, true);
                                          }}
                                      >{option.display}</Radio>
                                  </div>
                              {/each}
                          </div>
                      {/each}
                  </div>
                  <div>
                      <h6 class="text-xs text-gray-500 mb-1">Other Segments</h6>
                      {#each otherSegments as field}
                          <div class="mb-0 relative">
                              <Checkbox
                                  bind:checked={fieldStates[availableFields.indexOf(field)]}
                                  on:change={() => updateSelectedFields(availableFields.indexOf(field),
                                                fieldStates[availableFields.indexOf(field)])}
                                  disabled={checkboxStates[availableFields.indexOf(field)].disabled}
                                  class={checkboxStates[availableFields.indexOf(field)].disabled ? 'opacity-50 cursor-not-allowed text-gray-400 p-1 -ml-1' : 'hover:bg-gray-200 rounded-md transition-colors p-1 -ml-1'}
                              >{getDisplayName(field)}</Checkbox>
                              {#if checkboxStates[availableFields.indexOf(field)].tooltip}
                                  <Tooltip 
                                      color="red" 
                                      placement="right"
                                      class="max-w-[200px] min-w-[150px] whitespace-normal break-words"
                                  >
                                      {checkboxStates[availableFields.indexOf(field)].tooltip}
                                  </Tooltip>
                              {/if}
                          </div>
                      {/each}
                  </div>
              </div>

              <div>
                  <h5 class="text-sm font-medium text-gray-600 mb-2">Dimensions</h5>
                  {#each dimensionFields as field}
                      <div class="mb-0">
                          <Checkbox
                              bind:checked={fieldStates[availableFields.indexOf(field)]}
                              on:change={() => updateSelectedFields(availableFields.indexOf(field),
                                            fieldStates[availableFields.indexOf(field)])}
                              class={checkboxStates[availableFields.indexOf(field)].disabled ? 'opacity-50 cursor-not-allowed text-gray-400 p-1 -ml-1' : 'hover:bg-gray-200 rounded-md transition-colors p-1 -ml-1'}
                          >{getDisplayName(field)}</Checkbox>
                      </div>
                  {/each}
              </div>

              <!-- Metrics section -->
              <div>
                  <h5 class="text-sm font-medium text-gray-600 mb-2">Metrics</h5>
                  
                  <!-- Primary Metrics -->
                  <div class="mb-4">
                      <button 
                          class="text-xs text-gray-500 flex items-center mb-1 hover:bg-gray-200 rounded-md transition-colors p-1 w-full" 
                          on:click={() => showCommonMetrics = !showCommonMetrics}
                      >
                          <span class="mr-1">{showCommonMetrics ? '▼' : '▶'}</span>
                          Common Metrics
                      </button>
                      {#if showCommonMetrics}
                          {#each primaryMetrics as field}
                              <div class="mb-0 ml-4 relative">
                                  <Checkbox
                                      bind:checked={fieldStates[availableFields.indexOf(field)]}
                                      on:change={() => updateSelectedFields(availableFields.indexOf(field),
                                                    fieldStates[availableFields.indexOf(field)])}
                                      disabled={checkboxStates[availableFields.indexOf(field)].disabled}
                                      class={checkboxStates[availableFields.indexOf(field)].disabled ? 'opacity-50 cursor-not-allowed text-gray-400' : 'hover:bg-gray-200 rounded-md transition-colors p-1 -ml-1'}
                                  >{getDisplayName(field)}</Checkbox>
                                  {#if checkboxStates[availableFields.indexOf(field)].tooltip}
                                      <Tooltip 
                                          color="red" 
                                          placement="right"
                                          class="max-w-[200px] min-w-[150px] whitespace-normal break-words"
                                      >
                                          {checkboxStates[availableFields.indexOf(field)].tooltip}
                                      </Tooltip>
                                  {/if}
                              </div>
                          {/each}
                      {/if}
                  </div>

                  <!-- Secondary Metrics -->
                  <div class="mb-4">
                      <button 
                          class="text-xs text-gray-500 flex items-center mb-1 hover:bg-gray-200 rounded-md transition-colors p-1 w-full" 
                          on:click={() => showSecondaryMetrics = !showSecondaryMetrics}
                      >
                          <span class="mr-1">{showSecondaryMetrics ? '▼' : '▶'}</span>
                          Additional Metrics
                      </button>
                      {#if showSecondaryMetrics}
                          {#each secondaryMetrics as field}
                              <div class="mb-0 ml-4 relative">
                                  <Checkbox
                                      bind:checked={fieldStates[availableFields.indexOf(field)]}
                                      on:change={() => updateSelectedFields(availableFields.indexOf(field),
                                                    fieldStates[availableFields.indexOf(field)])}
                                      disabled={checkboxStates[availableFields.indexOf(field)].disabled}
                                      class={checkboxStates[availableFields.indexOf(field)].disabled ? 'opacity-50 cursor-not-allowed text-gray-400 p-1 -ml-1' : 'hover:bg-gray-200 rounded-md transition-colors p-1 -ml-1'}
                                  >{getDisplayName(field)}</Checkbox>
                                  {#if checkboxStates[availableFields.indexOf(field)].tooltip}
                                      <Tooltip 
                                          color="red" 
                                          placement="right"
                                          class="max-w-[200px] min-w-[150px] whitespace-normal break-words"
                                      >
                                          {checkboxStates[availableFields.indexOf(field)].tooltip}
                                      </Tooltip>
                                  {/if}
                              </div>
                          {/each}
                      {/if}
                  </div>

                  <!-- Tertiary Metrics -->
                  <div class="mb-4">
                      <button 
                          class="text-xs text-gray-500 flex items-center mb-1 hover:bg-gray-200 rounded-md transition-colors p-1 w-full" 
                          on:click={() => showTertiaryMetrics = !showTertiaryMetrics}
                      >
                          <span class="mr-1">{showTertiaryMetrics ? '▼' : '▶'}</span>
                          Advanced Metrics
                      </button>
                      {#if showTertiaryMetrics}
                          {#each tertiaryMetrics as field}
                              <div class="mb-0 ml-4 relative">
                                  <Checkbox
                                      bind:checked={fieldStates[availableFields.indexOf(field)]}
                                      on:change={() => updateSelectedFields(availableFields.indexOf(field),
                                                    fieldStates[availableFields.indexOf(field)])}
                                      disabled={checkboxStates[availableFields.indexOf(field)].disabled}
                                      class={checkboxStates[availableFields.indexOf(field)].disabled ? 'opacity-50 cursor-not-allowed text-gray-400 p-1 -ml-1' : 'hover:bg-gray-200 rounded-md p-1 -ml-1'}
                                  >{getDisplayName(field)}</Checkbox>
                                  {#if checkboxStates[availableFields.indexOf(field)].tooltip}
                                      <Tooltip 
                                          color="red" 
                                          placement="right"
                                          class="max-w-[200px] min-w-[150px] whitespace-normal break-words"
                                      >
                                          {checkboxStates[availableFields.indexOf(field)].tooltip}
                                      </Tooltip>
                                  {/if}
                              </div>
                          {/each}
                      {/if}
                  </div>
              </div>
          </div>
      </div>
    </div>
  </div>
{/if}

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
