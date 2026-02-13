<script lang="ts">
  import { writable } from 'svelte/store';
  import { serverUrl, receiveData, selectedTable, interactionView, displayLayout, messageStore } from '@store';
  import { resetInteractions, currentFlow } from '@store';
  import { Tooltip, Button } from 'flowbite-svelte';
  import { securedFetch } from '$lib/apiUtils';

  import StyleTemplate from './helpers/styleTemplate.svelte';
  import InteractivePanel from './components/interactiveComp.svelte';
  export let target = 'row';
  let tabColsItems = [];

  let batchNumber = 0;
  let confidenceLevel = 0;
  let numRemaining = -1;
  let chosenMethod = {name: 'manual', priority: 'N/A'};

  let automaticDetails = {title: 'Automatic Merge', type: 'desc', choices: {'description': 'Based on your guidance from the previous batches, Dana will resolve the remaining merge conflicts automatically for you.'},
    start: {'description': "Using intelligent machine learning algorithms, Dana will resolve merge conflicts automatically for you."}};
  let manualDetails = {title: 'Next Batch', type: 'desc', choices: {'description':
    "Review 10 more examples of merge conflicts, which will help train Dana to deal with them independently later."},
    start: {'description': "Review 10 examples of merge conflicts, which will be used to improve Dana's ability to resolve the rest."}};
  
  $: if ($interactionView.content && $resetInteractions) {
    const { content } = $interactionView;
    tabColsItems = content['selected'];
    batchNumber = content['batch_number'];
    confidenceLevel = Math.round(content['confidence_level'] * 1000) / 10;
    numRemaining = content['num_remaining'];

    if (batchNumber == 1) {
      automaticDetails.choices['description'] = 'Based on your guidance from the previous batch, Dana will resolve the remaining merge conflicts automatically for you.';
    }
    $resetInteractions = false;
  }

  function updateMethod(event) {
    chosenMethod.name = event.detail.name;
  }

  function addUserUtterance() {
    let messageOptions = {
      'automatic': 'Please resolve the remaining merge conflicts automatically for me.',
      'manual': 'I will review 10 more examples of merge conflicts to improve accuracy.'
    }
    messageStore.set({
      message: { type: 'text', content: messageOptions[chosenMethod.name] },
      userId: 'user', time: new Date()
    });
  }

  function handleFinalize() {
    const progressPayload = { 
      flowType: target === 'row' ? 'Clean(dedupe)' : 'Transform(join)',
      stage: 'combine-progress',
      selected: tabColsItems,
      method: chosenMethod.name };
    currentFlow.set(null);

    addUserUtterance();
    securedFetch(`${serverUrl}/interactions/merge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(progressPayload)
    }).then(res => res.json())
      .then(data => {receiveData(data)})
      .catch(err => console.log(err));
  }

</script>

{#if batchNumber === 0}
<InteractivePanel title="Remove Duplicate Users"
  subtitle="To have Dana immediately merge all rows, select the 'Automatic Merge' option. Alternatively, to obtain a higher confidence level before merging, select the 'First Batch' option to manually review a few."
  onAccept={handleFinalize} acceptLabel="Get Started"
  index=0 total=0>
  <div class="mx-auto mt-1 grid grid-cols-3 gap-2 justify-between">

    <!-- Automatic Merge -->
    <StyleTemplate on:update={updateMethod} name='automatic' chosenStyle={chosenMethod}
      icon='automatic' customClass='p-2'
      title={automaticDetails.title}
      styleType={automaticDetails.type}
      choices={automaticDetails.start}/>

    <!-- Confidence Level -->
    <div class="p-4 flex flex-col items-center text-center justify-center text-slate-700">
      <p class="signature text-5xl">{confidenceLevel}%</p>
      <p class="signature my-3 mx-1 text-xl">Confidence Level</p>
      <Tooltip placement='bottom'>Measures how confident Dana would merge the remaining rows the same way that you would.</Tooltip>
    </div>

    <!-- Next Batch -->
    <StyleTemplate on:update={updateMethod} name='manual' chosenStyle={chosenMethod}
      icon='manual' customClass='p-2'
      title="First Batch"
      styleType={manualDetails.type}
      choices={manualDetails.start}/>

  </div>
</InteractivePanel>

{:else}
<InteractivePanel title="Remove Duplicate Users" 
  subtitle="Based on your input, Dana is now {confidenceLevel}% confident in handling the remaining {numRemaining} examples. Select 'Automatic Merge' to do that or select 'Next Batch' to review the next set of examples manually."
  onAccept={handleFinalize} acceptLabel="Next Step"
  index=0 total=0>
  <div class="mx-auto mt-1 grid grid-cols-3 gap-2 justify-between">

    <!-- Automatic Merge -->
    <StyleTemplate on:update={updateMethod} name='automatic' chosenStyle={chosenMethod}
      icon='automatic' customClass='p-2'
      title={automaticDetails.title}
      styleType={automaticDetails.type}
      choices={automaticDetails.choices}/>

    <!-- Confidence Level -->
    <div class="p-4 ml-2 flex flex-col items-center text-center justify-center text-slate-700">
      <p class="signature text-5xl">{confidenceLevel}%</p>
      <p class="signature my-3 mx-1 text-xl">Confidence Level</p>
    </div>

    <!-- Next Batch -->
    <StyleTemplate on:update={updateMethod} name='manual' chosenStyle={chosenMethod}
      icon='manual' customClass='p-2'
      title={manualDetails.title}
      styleType={manualDetails.type}
      choices={manualDetails.choices}/>

  </div>
</InteractivePanel>
{/if}

<style>
  .signature {
    font-family: 'Open Sans', Tahoma, 'Trebuchet MS';
  }
</style>