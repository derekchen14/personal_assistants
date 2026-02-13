<script>
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
  let selectedOption = ''; // Initialize the selected option

  // Update button configuration based on component state
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

  // Common Salesforce objects that users might want to import
  const options = ['accounts', 'contacts', 'opportunities', 'leads', 'cases'];
  let optionStates = options.map(() => false);
  
  function updateSelectedOption(index, checked) {
    if (checked) {
      selectedOption = options[index];
      optionStates = options.map((_, i) => i === index);
    }
  }

  async function disconnectSalesforce() {
    try {
      const response = await fetch('/api/v1/disconnectIntegration/salesforce', {
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
      displayAlert('error', 'Failed to disconnect from Salesforce');
    }
  }
  
  function handleImport() {
    const config = {
      scope: selectedOption
    };
    getResources('salesforce', config);
  }
</script>

<div class="flex flex-col h-full overflow-y-auto">
  <!-- Scrollable content area -->
  <ConnectorHeader 
    title="Salesforce"
    on:disconnect={disconnectSalesforce}
    showRefresh={false}
  />

  <div class="flex flex-col flex-1 p-4">
    <h3 class="text-lg font-medium text-gray-900 mb-4">Select Data Type</h3>
    <div class="flex-1 overflow-y-auto w-full max-w-md mx-auto">
      <div class="grid grid-cols-1 gap-2">
        {#each options as option, i}
          <div 
            class="flex items-center p-3 border rounded-lg hover:bg-gray-50 cursor-pointer {selectedOption === option ? 'border-blue-500 bg-blue-50' : 'border-gray-200'}"
            on:click={() => selectedOption = option}
          >
            <input 
              type="radio" 
              bind:group={selectedOption} 
              value={option} 
              class="mr-3"
              id={`option-${i}`}
            >
            <label 
              for={`option-${i}`}
              class="flex-grow capitalize cursor-pointer"
            >{option}</label>
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
