<script lang="ts">
  import { writable } from 'svelte/store';
  import { serverUrl, receiveData, selectedTable, interactionView, displayLayout } from '@store';
  import { resetInteractions, currentFlow, currentStage } from '@store';
  import { securedFetch } from '$lib/apiUtils';

  import CycleButtons from './helpers/cycleButtons.svelte';
  import InteractivePanel from './components/interactiveComp.svelte';
  let selectedEntities = [];

  let cardsetIndex = 0;
  let batchNumber = 0;
  let confidenceLevel = 0;
  let cardSet = {'left': [], 'right': []};
  let numCards = {'left': 0, 'right': 0};
  let chosenCards = {'left': 0, 'right': 0};
  let rowIds = {'left': [], 'right': []};
  let tableNames = {'left': '', 'right': ''};
  let cardWidth = '';
  
  $: if ($interactionView.content && $resetInteractions) {
    const { content } = $interactionView;
    selectedEntities = content['selected'];
    cardsetIndex = content['cardset_index'] - 1;  // interactive component uses 0-indexed cards
    batchNumber = content['batch_number'];
    confidenceLevel = content['confidence_level'];
    chosenCards = {'left': 0, 'right': 0};  // reset the chosen cards to the first ones

    // Parse out the card-sets and the number of cards in each set
    const allCardSets = content['cardsets'];
    cardSet['left'] = allCardSets[cardsetIndex]['left'];
    cardSet['right'] = allCardSets[cardsetIndex]['right'];
    rowIds['left'] = allCardSets[cardsetIndex]['row_ids']['left'];
    rowIds['right'] = allCardSets[cardsetIndex]['row_ids']['right'];
    numCards['left'] = cardSet['left'].length;
    numCards['right'] = cardSet['right'].length;

    const currentTables = allCardSets[cardsetIndex]['tables']
    tableNames['left'] = currentTables[0];
    tableNames['right'] = currentTables[1] || currentTables[0];  // use the second table if one exists

    // Calculate the maximum length of the content of both left and right cards
    const contentSize = ['left', 'right'].reduce((maxLen, side) => {
      const sideMax = cardSet[side].reduce((sideMaxLen, card) => {
        return Math.max(sideMaxLen, ...Object.entries(card).map(([key, value]) => 
          `${key}: ${value}`.length));
      }, 0);
      return Math.max(maxLen, sideMax);
    }, 0);
    // Find the nearest Tailwind width class for the given content size, max out at w-72
    const tailwindWidth = [56, 60, 64, 72].find(width => Math.ceil(contentSize * 2) <= width) || 72;
    cardWidth = `w-${tailwindWidth}`;

    $resetInteractions = false;
  }

  function cycleCard(event) {
    const side = event.detail.side;
    const direction = event.detail.direction;

    if (direction === 'up') {
      chosenCards[side] = ((chosenCards[side] - 1 + numCards[side]) % numCards[side]);
    } else if (direction === 'down') {
      chosenCards[side] = ((chosenCards[side] + 1) % numCards[side]);
    }
  }

  function switchTableView(side) {
    const tabName = tableNames[side];
    selectedTable.set(tabName);
  }

  function previousCard() { completeMerge('back'); }
  function keepSeparate() { completeMerge('separate'); }
  function mergeTogether() { completeMerge('merge'); }

  function completeMerge(res) {
    const cardPayload = {
      flowType: 'Transform(join)',
      stage: 'combine-cards',
      selected: selectedEntities,
      resolution: res
    };
    // assign the chosen row ids onto each side of the payload
    let leftRowId = rowIds['left'][chosenCards['left']];
    let rightRowId = rowIds['right'][chosenCards['right']];
    cardPayload.chosen = { left: [leftRowId], right: [rightRowId] };

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
  title="Resolve Merge Conflicts" subtitle="Please decide if the rows are actual duplicates to merge together, or different rows to keep separate. You can use the up/down triangles to view other potential matches."
  onReject={keepSeparate} rejectLabel="Keep Separate"
  onAccept={mergeTogether} acceptLabel="Merge Together"
  index={cardsetIndex} total=10 showBack=true on:back={previousCard} customClass="my-1">

  <div class="flex justify-center items-start gap-3 text-sm xl:gap-5 xl:text-base w-full">
    <CycleButtons side="left" {chosenCards} {numCards} on:cycle={cycleCard} />

    <!-- Left Cards -->
    <div class="{cardWidth} xl:w-2/5 overflow-x-auto border border-slate-600 bg-white px-3 py-4 shadow-md"
      on:click={() => switchTableView('left')}>
      {#each Object.entries(cardSet['left'][chosenCards['left']]) as [colName, rowValue]}
        <div class="entry">
          <span class="font-medium mr-1">{colName}:</span>{rowValue}
        </div>
      {/each}
    </div>

    <!-- Card Divider -->
    <div class="divider w-1 bg-blue-800 rounded"></div>

    <!-- Right Cards -->
    <div class="{cardWidth} xl:w-2/5 overflow-x-auto border border-slate-600 bg-white px-3 py-4 shadow-md"
      on:click={() => switchTableView('right')}>
      {#each Object.entries(cardSet['right'][chosenCards['right']]) as [colName, rowValue]}
        <div class="entry">
          <span class="font-medium mr-1">{colName}:</span>{rowValue}
        </div>
      {/each}
    </div>

    <CycleButtons side="right" {chosenCards} {numCards} on:cycle={cycleCard} />
  </div>
</InteractivePanel>

<span class="w-56 w-60 w-64 w-72"></span>  <!-- To prevent Tailwind CSS purging  -->
<style>
  .divider {
    height: 120%;
    margin: -1em 0;
  }
</style>