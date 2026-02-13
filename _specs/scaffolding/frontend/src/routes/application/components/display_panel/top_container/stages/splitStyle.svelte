<script lang="ts">
  import { writable } from 'svelte/store';
  import { serverUrl, receiveData, interactionView, displayLayout,resetInteractions, currentFlow, messageStore } from '@store';
  import { securedFetch } from '$lib/apiUtils';

  import { rowStyleDetails, colStyleDetails } from './helpers/styleDetails.js';
  import StyleTemplate from './helpers/styleTemplate.svelte';
  import CustomStyle from './helpers/customStyleTemplate.svelte';
  import InteractivePanel from './components/interactiveComp.svelte';
  export let target = 'row';

  let sourceEntity = {};
  let delimiter = '';
  let targetEntities = [];
  let titleText = '';
  let subtitleText = '';

  let chosenStyle = {'name': '', 'setting': ''};
  let expanded = writable(false);

  $: if ($interactionView.content && $resetInteractions) {
    const { flowType, content } = $interactionView;
    sourceEntity = content['source_entity']; // selected tables and columns for merging (Array)
    delimiter = content['delimiter'];   // styles ordered by likelihood (Array)
    targetEntities = content['target_entities'];   // styles ordered by likelihood (Array)

    // set the default style to the first style in the list
    chosenStyle['name'] = rankedStyles[0];
    $resetInteractions = false;
  }

  function handleToggle(event) {
    if (event.detail) {
      expanded.set(true);
      displayLayout.set('top');
    } else {
      expanded.set(false);
      displayLayout.set('split');
    }
  }

  function updateStyle(event) {
    chosenStyle.name = event.detail.name;
    if (event.detail.setting && event.detail.setting !== 'N/A') {
      chosenStyle.setting = event.detail.setting;
    } else {
      chosenStyle.setting = '';
    }
  }

  function addUserUtterace() {
    let message = '';
    let choices = styleDetails[chosenStyle.name].choices;
    message = 'description' in choices ? choices['description'] : choices[chosenStyle.setting];

    messageStore.set({
      message: { type: 'text', content: message },
      userId: 'user', time: new Date()
    });
  }

  function handleGoBack() {
    const stylePayload = {
      flowType: target === 'column' ? 'Transform(merge)' : 'Clean(dedupe)',
      stage: 'cancel', selected: tabColsItems, style: {} };
    currentFlow.set(null);
    displayLayout.set('split');

    securedFetch(`${serverUrl}/interactions/merge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(stylePayload)
    }).then(res => res.json())
      .then(data => {receiveData(data)})
      .catch(err => console.log(err));
  }

  function handleFinish() {
    const stylePayload = {
      flowType: target === 'column' ? 'Transform(merge)' : 'Clean(dedupe)',
      stage: 'merge-style', selected: tabColsItems, style: chosenStyle };
    currentFlow.set(null);
    displayLayout.set('split');
    // console.log('stylePayload', stylePayload)

    addUserUtterace();
    securedFetch(`${serverUrl}/interactions/merge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(stylePayload)
    }).then(res => res.json())
      .then(data => {receiveData(data)})
      .catch(err => console.log(err));
  }
 
  $: if (target === 'column') {
    titleText = 'How to Merge Columns';
    subtitleText = 'Choose a method to merge the selected columns together. To see more choices, click the Expand button in the bottom left corner.';
   } else {
    titleText = 'Handle Merge Conflicts';
    subtitleText = "Please decide how you would like to resolve merge conflicts when combining users. To see more choices, click the Expand button in the bottom left corner.";
  }

</script>

<InteractivePanel
  title={titleText} subtitle={subtitleText}
  onReject={handleGoBack} rejectLabel="Back"
  onAccept={handleFinish} acceptLabel="Finish"
  index=1 total=3 showToggle=true on:toggle={handleToggle}>

  <div class="mx-auto grid grid-cols-3 gap-2 justify-between {$expanded ? 'mt-1' : '-mt-2'}">
  {#each rankedStyles.slice(0, $expanded ? 12 : 3) as style}
    <StyleTemplate on:update={updateStyle} name={style} chosenStyle={chosenStyle}
      icon={styleDetails[style].icon}
      title={styleDetails[style].title}
      example={styleDetails[style].example}
      styleType={styleDetails[style].type}
      choices={styleDetails[style].choices}/>
  {/each}
  </div>

</InteractivePanel>