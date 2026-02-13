<script>
  import { selectSheet, availableSheets, initializeSocket, activeConnector, agentStatus, disconnectionMessage, connectionStatus, utteranceHistory } from '@store';
  import { displayAlert } from '@alert';
  import AlertBox from '../../shared/alertBox.svelte';
  import DataSelector from './DataSelector.svelte';
  import { securedFetch } from '$lib/apiUtils';
  import { serverUrl } from '@store';
  import { onMount } from 'svelte';
  
  let hoveredSheet = null;
  let pastConversations = [];
  let loading = {
    conversations: true
  };

  onMount(async () => {
    try {
      // Clear the utterance history when we load the welcome message
      utteranceHistory.set([]);
      // Fetch past conversations
      const conversationsResponse = await securedFetch(`${serverUrl}/conversations`);
      if (conversationsResponse.ok) {
        pastConversations = await conversationsResponse.json();
      }
    } catch (error) {
      console.error('Failed to fetch data:', error);
    } finally {
      loading.conversations = false;
    }
  });

  async function localSheetSelect(spreadsheet) {
    const socketConnection = await initializeSocket();
    if (socketConnection) {
      selectSheet(spreadsheet);
      $activeConnector = null;
    } else {
      displayAlert('error', 'Failed to load spreadsheet due to socket connection issue.');
    }
  }

  async function selectConversation(conversation) {
    // Navigate to the conversation route
    window.location.href = `/application/conversation/${conversation.id}`;
  }

  async function deleteConversation(conversationId, event) {
    event.stopPropagation(); // Prevent triggering the conversation selection
    try {
      const response = await securedFetch(`${serverUrl}/conversation/${conversationId}`, {
        method: 'DELETE'
      });
      
      if (response.ok) {
        // Remove the conversation from the list
        pastConversations = pastConversations.filter(conv => conv.id !== conversationId);
        displayAlert('success', 'Conversation deleted successfully');
      } else {
        displayAlert('error', 'Failed to delete conversation');
      }
    } catch (error) {
      console.error('Failed to delete conversation:', error);
      displayAlert('error', 'Failed to delete conversation');
    }
  }

  // Show error message when agent is disconnected
  $: if ($agentStatus === false && $connectionStatus === 'disconnected' && $disconnectionMessage) {
    displayAlert('error', $disconnectionMessage, true /* Persistent */);
  }
</script>

<div class="m-8 p-0 md:p-2 lg:px-4 lg:py-2">
  <AlertBox />

  <p class="font-medium text-xl mb-1">Welcome to Soleda!</p>

  {#if loading.conversations}
    <div class="animate-pulse">
      <div class="h-4 bg-gray-200 rounded w-3/4 mb-4"></div>
      <div class="h-4 bg-gray-200 rounded w-1/2"></div>
    </div>
  {:else if pastConversations.length > 0}
    <p class="my-2">
      Pick up where you left off by selecting a past conversation, or try one of our sample datasets:
    </p>
    <DataSelector
      title="Your Past Conversations:"
      items={pastConversations}
      onSelect={selectConversation}
      onDelete={deleteConversation}
      loading={loading.conversations}
    />
    <DataSelector
      title="Or select one of our pre-loaded spreadsheets:"
      items={$availableSheets}
      onSelect={localSheetSelect}
    />
  {:else}
    <p class="my-2">
      To get started, select one of our pre-loaded sample spreadsheets below, or upload your own CSV files by dragging into the bottom panel.
    </p>
    <DataSelector title="" items={$availableSheets} onSelect={localSheetSelect}/>
  {/if}

</div>