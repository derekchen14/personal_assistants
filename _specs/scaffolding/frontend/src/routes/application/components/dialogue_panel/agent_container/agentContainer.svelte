<script>
  import { onMount } from 'svelte';
  import { fileSelectorView, chatActive, oauthSuccess, displayLayout, showResetModal, activeConnector } from '@store';
  import { Dropdown, DropdownItem, DropdownDivider } from 'flowbite-svelte';

  import Avatar from '../../shared/avatar.svelte';
  import AddNewButton from '../../shared/addNewButton.svelte';
  import OptionsButton from '../../shared/optionsButton.svelte';

  let dropdownOpen = false;

  const activateConnector = (connector) => {
    dropdownOpen = false;
    if (connector === 'upload') {
      $oauthSuccess = false; // Reset oauthSuccess when switching to upload
    }
    $activeConnector = connector;
    // Set layout to bottom for specified connectors
    $displayLayout = ['google', 'drive', 'ga4', 'hubspot', 'facebook', 'salesforce'].includes(connector) ? 'bottom' : 'split';
  };

  const openFileSelector = () => {
    dropdownOpen = false;
    $fileSelectorView = true;
    $displayLayout = 'split';
  };

  async function addConnector(data_source) {
    try {
      const isConnected = await checkConnectionStatus(data_source);
      
      if (isConnected) {
        $oauthSuccess = true;
        activateConnector(data_source);
        return;
      }

      // If not connected, open the OAuth popup
      const messageHandler = async (event) => {        
        const normalizedSource = event.data.source.toLowerCase();
        
        if (event.data.type === 'oauth_success' && normalizedSource === `${data_source}-callback`) {
          $oauthSuccess = true;
          activateConnector(data_source);
          window.removeEventListener('message', messageHandler);
        }
      };

      window.addEventListener('message', messageHandler);
      const left = window.screenX + (window.outerWidth - 800) / 2;
      const top = window.screenY + (window.outerHeight - 600) / 2;

      const popup = window.open(`/api/v1/oauth/${data_source}`, `Connect to ${data_source}`,
                              `width=800,height=600,left=${left},top=${top}`);
    } catch (error) {
      console.error(`${data_source} operation failed:`, error);
      displayAlert(`error`, `Failed to perform ${data_source} operation`);
    }
  }

  async function checkConnectionStatus(data_source) {
    try {
      const connectionStatus = await fetch(`/api/v1/integrationStatus/${data_source}`, {
        credentials: 'include',
        headers: { 'Accept': 'application/json' }
      });
      
      const data = await connectionStatus.json();
      return data.connected;
    } catch (error) {
      console.error('Status check failed:', error);
      return false;
    }
  }

  const triggerReset = () => {
    dropdownOpen = false;
    showResetModal.set(true);
  };
  

  onMount(() => {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('oauth_success') === 'true') {
      $oauthSuccess = true;
      $displayLayout = 'bottom';
    }
  });
</script>

<div class="flex flex-row rounded-t-md items-center justify-between bg-slate-50
  border-b border-solid border-gray-300 p-2.5 pr-6">
  <div class="flex items-center gap-2">
    <Avatar showStatus={true} userId="agent" />
    <p class="signature-font text-xl {$chatActive ? 'text-slate-700' : 'text-slate-500'}">Dana</p>
  </div>

  <div class="flex w-8 justify-between">
    <div>
      <OptionsButton style="w-6 h-6 text-gray-600" />
      <Dropdown bind:open={dropdownOpen}>
        <DropdownItem on:click={openFileSelector}>Your Files</DropdownItem>
        <DropdownItem on:click={() => activateConnector('upload')}>Upload CSV</DropdownItem>
        <!-- <DropdownItem on:click={() => addConnector('amplitude')}>Amplitude</DropdownItem> -->
        <DropdownItem on:click={() => addConnector('salesforce')}>Salesforce</DropdownItem>
        <DropdownItem on:click={() => addConnector('ga4')}>GA4</DropdownItem>
        <DropdownItem on:click={() => addConnector('facebook')}>Facebook</DropdownItem>
        <DropdownItem on:click={() => addConnector('drive')}>Google Drive</DropdownItem>
        <DropdownItem on:click={() => addConnector('google')}>Google Ads</DropdownItem>
        <DropdownItem on:click={() => addConnector('hubspot')}>HubSpot</DropdownItem>        
        {#if $chatActive}
          <DropdownDivider /><DropdownItem on:click={triggerReset}>Reset Chat</DropdownItem>
        {/if}
      </Dropdown>
    </div>
  </div>
</div>
