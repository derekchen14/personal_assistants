<script lang="ts">
  import { writable } from 'svelte/store';
  import { serverUrl, receiveData, interactionView, displayLayout,resetInteractions, currentFlow, messageStore } from '@store';
  import { securedFetch } from '$lib/apiUtils';

  import { rowStyleDetails, colStyleDetails } from './helpers/styleDetails.js';
  import StyleTemplate from './helpers/styleTemplate.svelte';
  import CustomStyle from './helpers/customStyleTemplate.svelte';
  import InteractivePanel from './components/interactiveComp.svelte';

  let rankedStyles = [];
  let selectedEntities = [];
  let referenceColumns = {};
  let titleText = '';
  let subtitleText = '';

  let styleDetails = {};
  let chosenStyle = {'name': '', 'setting': ''};
  let expanded = writable(false);

  $: if ($interactionView.content && $resetInteractions) {
    const { flowType, content } = $interactionView;
    selectedEntities = content['selected'];   // selected tables and columns for merging (Array)
    rankedStyles = content['styles'];         // styles ordered by likelihood (Array)
    referenceColumns = content['reference'];    // default settings for style priorities (Object)

    // unpack the settings object
    const datetimeColumn = referenceColumns['time_col'];
    const binaryColumn = referenceColumns['binary_col'];
    styleDetails = flowType === 'Transform(merge)' ? colStyleDetails : rowStyleDetails;

    let earlier_desc = styleDetails.time.choices['earlier'];
    let later_desc = styleDetails.time.choices['later'];
    let positive_desc = styleDetails.binary.choices['positive'];
    let negative_desc = styleDetails.binary.choices['negative'];

    styleDetails.time.choices['earlier'] = earlier_desc.replace('<COL>', datetimeColumn);
    styleDetails.time.choices['later'] = later_desc.replace('<COL>', datetimeColumn);
    styleDetails.binary.choices['positive'] = positive_desc.replace('<COL>', binaryColumn);
    styleDetails.binary.choices['negative'] = negative_desc.replace('<COL>', binaryColumn);

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
    if (chosenStyle.name === 'customText' || chosenStyle.name === 'customNumber') {
      message = `Please merge the columns together using a custom formula to form a new value.`;
    } else {
      let choices = styleDetails[chosenStyle.name].choices;
      message = 'description' in choices ? choices['description'] : choices[chosenStyle.setting];
    }

    messageStore.set({
      message: { type: 'text', content: message },
      userId: 'user', time: new Date()
    });
  }

  function handleGoBack() {
    const stylePayload = { flowType: 'Clean(dedupe)', stage: 'cancel', selected: selectedEntities,
                            style: {} };
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
    const stylePayload = { flowType: 'Clean(dedupe)', stage: 'merge-style', selected: selectedEntities }

    if (chosenStyle.name === 'automatic') {
      chosenStyle.name = 'order';
      chosenStyle.setting = 'first';
    }
    if (['order', 'time', 'binary', 'subtract', 'divide', 'size', 'length', 'alpha'].includes(chosenStyle.name)) {
      if (!chosenStyle.setting) {
        let firstSetting = Object.keys(styleDetails[chosenStyle.name].choices)[0];
        chosenStyle.setting = firstSetting;
      }
    }

    stylePayload.style = chosenStyle;
    currentFlow.set(null);
    displayLayout.set('split');
    console.log('stylePayload', stylePayload)

    addUserUtterace();
    securedFetch(`${serverUrl}/interactions/merge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(stylePayload)
    }).then(res => res.json())
      .then(data => {receiveData(data)})
      .catch(err => console.log(err));
  }

</script>

<InteractivePanel
  title='Conflicting Duplicates' subtitle="Please decide how you would like to resolve merge conflicts when combining users. To see more choices, click the Expand button in the bottom left corner."
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

    {#if $expanded}
      <!-- Only support formulas with numbers for now
      <CustomStyle on:update={updateStyle} name='customText' chosenStyle={chosenStyle}/> -->
      <CustomStyle on:update={updateStyle} name='customNumber' chosenStyle={chosenStyle}/>
    {/if}
  </div>

</InteractivePanel>