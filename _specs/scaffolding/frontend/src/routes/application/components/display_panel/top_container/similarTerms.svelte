<script lang="ts">
  import { interactionView, serverUrl, receiveData, carouselIndex } from '@store';
  import { writable } from 'svelte/store';
  import { securedFetch } from '$lib/apiUtils';
  import { clickOutside } from './dropdown/clickOutside.js';
  import InteractivePanel from './stages/components/interactiveComp.svelte';

  import CheckIcon from '@lib/icons/Check.svelte';
  import XCircle from '@lib/icons/XCircle.svelte';
  import AddIcon from '@lib/icons/Add.svelte';
  const ordinals = ['first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh', 'eighth']

  let chosenIndex = writable(0);
  let termGroups = {};
  let groupKeys = [];
  let chosenTerm = '';
  let simTerms = [];
  let validTerms = []

  let carouselLength = 1;
  let maxChar = 0;
  let btnWidth = 100;
  let addingTerm = writable(false);
  let newTerm = writable('');

  $: if ($interactionView && groupKeys.length === 0) {
    termGroups = $interactionView.content;
    groupKeys = Object.keys(termGroups);
    carouselLength = groupKeys.length;

    // set the initial chosenTerm and simTerms
    chosenTerm = groupKeys[$carouselIndex];
    simTerms = termGroups[chosenTerm];
    maxChar = simTerms.reduce((max, term) => Math.max(max, term.length), 0);
    btnWidth = maxChar * 9 + 64;

    // unpack the valid terms
    const allTermsInColumn = $interactionView.valid;
    validTerms = allTermsInColumn.filter(term => !simTerms.includes(term));
  }

  // update the simTerm group when the carouselIndex changes
  $: if ($carouselIndex < groupKeys.length) {
    const currentTerm = groupKeys[$carouselIndex];
    simTerms = termGroups[currentTerm];
    chosenIndex.set(simTerms.indexOf(currentTerm));
  }
  // update the chosenTerm when the chosenIndex changes
  $: if ($chosenIndex < simTerms.length) {
    chosenTerm = simTerms[$chosenIndex];
  }

  function startAdd() {
    newTerm.set(validTerms[0])  // Pre-select the first term
    addingTerm.set(true)        // convert to a dropdown
  }

  const removeTerm = (index) => {
    simTerms.splice(index, 1);
    simTerms = [...simTerms];
  }

  function checkForSelectTerm() {
    termGroups[chosenTerm] = [...simTerms, $newTerm]
    addingTerm.set(false)
    newTerm.set(''); // Reset dropdown
  }

  const resolveTermGroup = (skip) => {
    // send simTerms to backend
    const entity = {tab: $interactionView.table, col: $interactionView.column, ver: true};
    const payload = {
      flowType: 'Detect(typo)',
      stage: 'select-pill',
      chosen: chosenTerm,
      source: entity,
      similar: skip ? [] : simTerms
    };

    const response = securedFetch(`${serverUrl}/interactions/resolve/typo`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    }).then(res => res.json())
      .then(data => {receiveData(data)})
      .catch(err => console.log(err));
  }
</script>

<InteractivePanel title="Potential Typos"
  subtitle={`This is the ${ordinals[$carouselIndex]} group of similar terms we found. Choose the term you want the others to merge into. Clicking [Finalize] will combine them into the chosen term: ${chosenTerm}.`}
  onAccept={() => resolveTermGroup(false)} acceptLabel="Finalize"
  onReject={() => resolveTermGroup(true)} rejectLabel="Skip"
  customClass="mb-2" index={$carouselIndex} total={carouselLength}>
  <div class="flex justify-center items-center font-medium flex-wrap gap-4 group w-full">

    {#each simTerms as term, i}
      {#if i === $chosenIndex}
        <button style={`width: ${btnWidth}px`} class='px-6 py-2 text-sky-700 bg-sky-500/30 border-2 border-sky-700 rounded-full simterm-button hover:bg-cyan-500/50 relative'> {term} <CheckIcon/>
        </button>
      {:else}
        <button style={`width: ${btnWidth}px`} class='px-6 py-2 text-sky-700 bg-sky-500/30 border-2 border-sky-700 rounded-full simterm-button hover:bg-cyan-500/50 relative' on:click={() => chosenIndex.set(i)} >
          <span class="close-icon">
            <XCircle on:click={() => removeTerm(i) } position="left-2.5 top-2.5" />
          </span>
          {term}
        </button> 
      {/if}
    {/each}

    <button on:click={startAdd} use:clickOutside={addingTerm} class="ml-3 px-3 w-22 text-green-700
      bg-green-700/10 border-2 border-green-700 cursor-pointer rounded simterm-button min-h-10 relative 
      transition-visibility duration-500 group-hover:visible invisible hover:bg-green-300">
      {#if $addingTerm} <!-- Convert to a dropdown -->
        <select bind:value={$newTerm} on:change={checkForSelectTerm}
          class="w-full h-full bg-slate-50/50 border-green-500">
          {#each validTerms as valTerm}
            <option value={valTerm}>{valTerm}</option>
          {/each}
        </select>
      {:else}           <!-- Show the Add button -->
        <AddIcon /> Add
      {/if}
    </button>

  </div>
</InteractivePanel>

<style>
  .close-icon {
    opacity: 0;  /* Default is to hide the icon */
    transition: opacity 0.2s ease-in-out;
  }
  .simterm-button:hover .close-icon {
    opacity: 1; /* Show the icon when the button is hovered */
  }
</style>