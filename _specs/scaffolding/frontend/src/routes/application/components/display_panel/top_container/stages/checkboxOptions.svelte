<script lang="ts">
  import { serverUrl, receiveData, interactionView, selectTab, messageStore } from '@store';
  import { resetInteractions, currentFlow } from '@store';
  import { displayAlert } from '@alert';
  import { securedFetch } from '$lib/apiUtils';

  import InteractivePanel from './components/interactiveComp.svelte';
  let stage = '';
  let proposedOptions = [];  // options that are pre-selected to be checked
  let possibleOptions = [];  // all available options

  // For table integration flow
  let sourceTabs = [];
  let mergedTab = '';
  export let tabReviewNeeded = false;

  $: if ($interactionView.content && $resetInteractions) {
    const { flowType, content } = $interactionView;

    if (tabReviewNeeded) {
      const sourceEntities = content['entities']['source'];
      sourceTabs = [...new Set( sourceEntities.map(entity => entity.tab) )];
      selectTab(sourceTabs[0]);

      const targetEntities = content['entities']['target'];
      mergedTab = targetEntities[0].tab;
    }

    proposedOptions = content['proposed'];
    possibleOptions = content['possible'];
    $currentFlow = flowType;
    $resetInteractions = false;
  }

  function addUserUtterance() {
    let message = '';
    if (tabReviewNeeded) {
      const oldTabs = sourceTabs.join(' and ');
      message = `Create a new table called ${mergedTab} that merges content from ${oldTabs}.`;
    } else {
      const numTerms = proposedOptions.length;
      message = `Please select these ${numTerms} valid terms to keep in the column.`;
    }

    messageStore.set({
      message: { type: 'text', content: message },
      userId: 'user', time: new Date()
    });
  }

  function changeCheckState(option) {
    const index = proposedOptions.indexOf(option);
    if (index === -1) {     // Option not in proposedOptions, so add it
      proposedOptions = [...proposedOptions, option];
    } else {                // Option already in proposedOptions, so remove it
      proposedOptions = proposedOptions.filter((_, i) => i !== index);
    }
  }

  const handleBack = () => {
    const payload = { flowType: $currentFlow, stage: 'cancel', checked: [], support: mergedTab };
    currentFlow.set(null);

    securedFetch(`${serverUrl}/interactions/checkbox`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(res => res.json())
      .then(data => {receiveData(data)})
      .catch(err => console.log(err));
  }

  function handleFinish() {
    if (tabReviewNeeded) {
      if (mergedTab.length < 3) {
        displayAlert('warning', 'The name of the new tab is too short, please provide a more descriptive name.');
        return;
      }
      if (proposedOptions.length < sourceTabs.length) {
        displayAlert('warning', 'At least one column must be selected from each of the source tables.');
        return; // Prevent further execution if no valid items are found
      }
    }

    const payload = { flowType: $currentFlow, stage: 'checkbox-opt', checked: proposedOptions, support: mergedTab };
    currentFlow.set(null);
    addUserUtterance();

    securedFetch(`${serverUrl}/interactions/checkbox`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(res => res.json())
      .then(data => {receiveData(data)})
      .catch(err => console.log(err));
  }
  // title="Columns for Integrated Table"
  // subtitle="Please review the new table name, and then select the columns to keep in this integrated table."
</script>

<InteractivePanel title="Valid Terms to Keep"
  subtitle="Please review the terms found in the column, and then check the ones which you consider valid."
  onReject={handleBack} rejectLabel="Back"
  onAccept={handleFinish} acceptLabel="Approve">

  <div class="flex flex-col w-full items-center m-2 mb-6">
    {#if tabReviewNeeded}
    <div class="mb-4 flex justify-center items-center w-full">    
      <span class="open-sans-font">New Tab Name: </span>
      <input type="text" class="w-1/3 p-1 m-2" bind:value={mergedTab} />
    </div>
    {/if}

    <div class="grid grid-cols-3 gap-2 ml-4">
      {#each possibleOptions as option}
        <div class="mr-2">
        <input type="checkbox" id={`column-${option}`}
            checked={proposedOptions.includes(option)} 
            on:change={() => changeCheckState(option)} />
        <label for={`column-${option}`}>{option}</label>
        </div>
      {/each}
    </div>
  <div>

</InteractivePanel>