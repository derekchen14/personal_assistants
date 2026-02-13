<script lang="ts">
  import { serverUrl, receiveData, interactionView, messageStore, currentFlow, resetInteractions } from '@store';
  import { displayAlert } from '@alert';
  import { securedFetch } from '$lib/apiUtils';

  import InteractivePanel from './components/interactiveComp.svelte';
  import EditIcon from '@lib/icons/dialogue/PencilSquare.svelte';

  let editMode = false;
  let originalQuery = '';
  let preparedQuery = '';
  let modifiedQuery = '';
  let flowName = '';

  $: if ($interactionView.content && $resetInteractions) {
    flowName = $interactionView.flowType;
    originalQuery = $interactionView.content;
    $resetInteractions = false;
  }

  function addUserUtterance() {
    messageStore.set({
      message: { type: 'text', content: 'Directly execute a modified query.' },
      userId: 'user', time: new Date()
    });
  }

  const enableModification = () => {
    editMode = true;
    if (preparedQuery.length === 0) {
      // limit to the actual query portion and perform transformations
      let queryOnly = originalQuery.substring(23);
      preparedQuery = queryOnly.replace(/&nbsp;&nbsp;/g, '  ').replace(/<br>/g, '\n');
      modifiedQuery = preparedQuery;
    }
  }

  const handleCancel = () => {
    editMode = false;
  }

  function editDistance() {
    let orig = preparedQuery.toLowerCase();
    let mod = modifiedQuery.toLowerCase();
    let dp = Array.from({ length: orig.length + 1 }, () => Array(mod.length + 1).fill(0));

    // Initialize first row and column
    for (let i = 0; i <= orig.length; i++) dp[i][0] = i;
    for (let j = 0; j <= mod.length; j++) dp[0][j] = j;

    for (let i = 1; i <= orig.length; i++) {
      for (let j = 1; j <= mod.length; j++) {
        if (orig[i - 1] === mod[j - 1]) {
          dp[i][j] = dp[i - 1][j - 1];
        } else {
          dp[i][j] = 1 + Math.min(dp[i - 1][j - 1], dp[i - 1][j], dp[i][j - 1]);
        }
      }
    }

    return dp[orig.length][mod.length];
  }

  function handleSubmit() {
    const payload = { flowType: flowName, language: 'sql' };

    // Only allow code edits of up 16 characters different from the original to prevent abuse
    if (editDistance() > 16) {
      displayAlert('warning', 'Only minor modifications to the query are allowed');
      return; // Exit the current iteration if the query is too different
    } else {
      payload.code = modifiedQuery;
      currentFlow.set(null);
    }

    addUserUtterance()
    securedFetch(`${serverUrl}/interactions/command/code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(response => response.json())
      .then(data => {receiveData(data)})
      .catch(error => console.log(error));
  }

</script>

{#if editMode}
  <InteractivePanel title="SQL Query" subtitle="" total=0
    onReject={handleCancel} rejectLabel="Cancel" onAccept={handleSubmit} acceptLabel="Submit">
    <textarea class="w-full h-40 p-2 border border-gray-300 rounded-lg"
      bind:value={modifiedQuery} placeholder="Enter your SQL query here"></textarea>
  </InteractivePanel>
{:else}
  <div class="group">
    <button class="float-right m-6 hidden group-hover:block"
      on:click={enableModification} aria-label="Edit SQL query">
      <EditIcon customSize='h-8 w-8'/>
    </button>
    <!-- eslint-disable-next-line svelte/no-at-html-tags -->
    <p class="text-lg m-10">{@html originalQuery}</p>
  </div>
{/if}