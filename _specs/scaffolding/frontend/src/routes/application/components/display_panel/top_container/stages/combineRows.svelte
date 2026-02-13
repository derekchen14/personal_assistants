<script lang="ts">
  import { writable } from 'svelte/store';
  import { serverUrl, receiveData, selectedTable, interactionView, displayLayout } from '@store';
  import { resetInteractions, currentFlow, currentStage } from '@store';
  import { displayAlert } from '@alert';
  import { securedFetch } from '$lib/apiUtils';

  import InteractivePanel from './components/interactiveComp.svelte';
  let selectedEntities = [];

  let cardsetIndex = 0;
  let batchNumber = 0;
  let numCardsets = 0;
  let confidenceLevel = 0;
  let chosenCard = -1;

  let cardSet = []
  let tabName = '';
  let rowIds = [];
  let cardWidth = '';

  const ordinals = ['first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh', 'eighth', 'ninth', 'tenth'];

  $: if ($interactionView.content && $resetInteractions) {
    const { content } = $interactionView;

    selectedEntities = content['selected'];
    cardsetIndex = content['cardset_index'] - 1;  // interactive component uses 0-indexed cards
    batchNumber = content['batch_number'];
    confidenceLevel = content['confidence_level'];
    chosenCard = -1;

    // Parse out the card-sets and the number of cardsets in the current batch
    const allCardSets = content['cardsets'];
    cardSet = allCardSets[cardsetIndex]['cards'];
    tabName = allCardSets[cardsetIndex]['tables'][0];
    rowIds = allCardSets[cardsetIndex]['row_ids'];
    numCardsets = allCardSets.length;

    // Calculate the maximum length of the content of duplicate row cards
    const contentSize = cardSet.reduce((maxLen, card) => {
      return Math.max(maxLen, ...Object.entries(card).map(([key, value]) => 
        `${key}: ${value}`.length));
    }, 0);
    // Find the nearest Tailwind width class for the given content size, max out at w-72
    const tailwindWidth = [56, 60, 64, 72].find(width => Math.ceil(contentSize * 2) <= width) || 72;
    cardWidth = `w-${tailwindWidth}`;
    $resetInteractions = false;
  }

  function previousCard() { completeMerge('back'); }
  function keepSeparate() { completeMerge('separate'); }
  function mergeTogether() { completeMerge('merge'); }

  function completeMerge(res) {
    const cardPayload = { flowType: 'Clean(dedupe)', stage: 'combine-cards', selected: selectedEntities, resolution: res};
    
    if (res === 'merge') {
      // if resolution is merge and chosen card is not selected, then throw a warning
      if (chosenCard < 0) {
        displayAlert('warning', 'Please select the primary row you want to keep');
        return;
      }
      cardPayload.chosen = {
        retain: [rowIds[chosenCard]],
        retire: rowIds.filter((_, index) => index !== chosenCard)
      };
    } else {
      // if resolution is separate (or back), then we are retaining all rows
      cardPayload.chosen = { retain: rowIds, retire: [] };
    }

    // if all cardsets have been processed, then move to model training and display a loading screen
    if (cardsetIndex > 8) {
      $currentStage = 'model-learning';
      $currentFlow = 'loading';
    }

    securedFetch(`${serverUrl}/interactions/merge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cardPayload)
    }).then(res => res.json())
      .then(data => {receiveData(data)})
      .catch(err => console.log(err));
  }
</script>

<InteractivePanel
  title="Identify Duplicates" subtitle={`This is the ${ordinals[cardsetIndex]} set of potential duplicates we found. Please select on the row you want to keep, then click 'Merge Together'. If the rows are not duplicates, then click 'Keep Separate'.`}
  onReject={keepSeparate} rejectLabel="Keep Separate"
  onAccept={mergeTogether} acceptLabel="Merge Together"
  index={cardsetIndex} total={numCardsets} showBack=true on:back={previousCard} customClass="my-1">

  <div class="flex justify-center items-start gap-5 text-sm xl:gap-8 xl:text-base w-full">

    {#each cardSet as singleCard, cardIndex}
      <div class="{cardWidth} xl:w-2/5 overflow-x-auto rounded-lg px-3 py-3 mx-2 shadow-md cursor-pointer
      transition duration-300 ease-in-out hover:shadow-xl
      {cardIndex === chosenCard ? 'bg-emerald-200 border-4 border-emerald-600' : 'my-1 bg-white border border-slate-600'}"
      on:click={() => chosenCard = cardIndex}>
        {#each Object.entries(singleCard) as [colName, rowValue]}
        <div class="entry">
          <span class="font-medium mr-1">{colName}:</span>{rowValue}
        </div>
        {/each}
      </div>
    {/each}

  </div>
</InteractivePanel>

<span class="w-56 w-60 w-64 w-72"></span>  <!-- To prevent Tailwind CSS purging  -->