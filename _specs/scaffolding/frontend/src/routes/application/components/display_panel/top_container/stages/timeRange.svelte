<script lang="ts">
  import { writable, get } from 'svelte/store';
  import { serverUrl, receiveData, tableView, sheetData, interactionView, panelVariables } from '@store';
  import { resetInteractions, currentFlow, messageStore } from '@store';
  import { securedFetch } from '$lib/apiUtils';
  import InteractivePanel from './components/interactiveComp.svelte';
  
  const timeOptions = {
    '1-day': 'Today',
    '0.5-week': 'Current week',
    '1-week': 'Last 7 days',
    '2-week': 'Last 14 days',
    '1-month': 'Past month',
    '1-year': 'Past year',
    'all': 'All time (ie. no time restriction)'
  };

  let selectedTime = '';   // choose from the 7 options above or 'custom'
  let fromDate = new Date(new Date().setDate(1)).toISOString().substring(0, 10);  // Set default as start of the month
  let toDate = new Date().toISOString().substring(0, 10);  // Set default as current date
  let metricName = ''

  $: if ($interactionView.content && $resetInteractions) {
    const { flowType, content } = $interactionView;
    selectedTime = content['selected_time']
    metricName = content['metric_name']

    let metricAliases = content['aliases']
    if (metricAliases.length > 0) {
      metricName = metricAliases[0]
    }
    $resetInteractions = false;
  }

  function selectCustom() {
    selectedTime = 'custom';
  }

  function addUserUtterance() {
    let message = ''

    if (selectedTime == 'custom') {
      message = `Please focus on data from ${fromDate} to ${toDate}.`;
    } else if (selectedTime == 'all') {
      message = "Please use all available data without any restriction on the time range.";
    } else if (selectedTime == '1-day') {
      message = "Let's focus on just data from today";
    } else {
      let naturalTime = timeOptions[selectedTime];
      naturalTime = naturalTime.charAt(0).toLowerCase() + naturalTime.slice(1);
      message = `Let's focus on data from the ${naturalTime}.`;
    }

    messageStore.set({
      message: { type: 'text', content: message },
      userId: 'user', time: new Date()
    });
  }

  function showDatePicker(event) {
    const input = event.target;
    if (event.clientX <= input.getBoundingClientRect().right) {
      input.focus();
      input.showPicker();
    }
  }

  const handleBack = () => {
    const metricPayload = { flowType: 'Select(analyze)', stage: 'time-range', time: {} };
    currentFlow.set(null);

    securedFetch(`${serverUrl}/interactions/metric/two`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(metricPayload)
    }).then(res => res.json())
      .then(data => {receiveData(data)})
      .catch(err => console.log(err));
  }

  function handleFinish() {
    const metricPayload = { flowType: 'Select(analyze)', stage: 'time-range' };
    metricPayload.time = { selected: selectedTime, from_date: fromDate, to_date: toDate };
    currentFlow.set(null);

    addUserUtterance()
    securedFetch(`${serverUrl}/interactions/metric/two`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(metricPayload)
    }).then(res => res.json())
      .then(data => {receiveData(data)})
      .catch(err => console.log(err));
  }
</script>

<InteractivePanel
  title="Time Range Selection" subtitle={`Please choose the time frame for calculating the ${metricName} metric.`}
  onReject={handleBack} rejectLabel="Back"
  onAccept={handleFinish} acceptLabel="Finish">

  <div class="flex flex-col w-full items-left m-4 mb-6">
  <div class="grid grid-cols-2 gap-4">

    <div class="col-span-1">
      {#each Object.entries(timeOptions) as [timeKey, option]}
        <label class="flex items-center">
          <input type="radio"bind:group={selectedTime} value={timeKey} />
          <span class="ml-4">{option}</span>
        </label>
      {/each}
    </div>

    <div class="col-span-1">
      <label class="flex items-center">
        <input type="radio" bind:group={selectedTime} value="custom" />
        <span class="ml-4">Custom range</span>
      </label>
      <!-- Date Pickers -->
      <div class="flex flex-col space-y-2 mt-2" on:click={selectCustom}>
        <div>
          <label for="fromDate">From:</label>
          <input id="fromDate" type="date" bind:value={fromDate} class="border-gray-300 rounded p-1" 
            on:click={showDatePicker}/>
        </div>
        <div>
          <label for="toDate">To:</label>
          <input id="toDate" type="date" bind:value={toDate} class="border-gray-300 rounded p-1"
            on:click={showDatePicker}/>
        </div>
      </div>
    </div>

  </div>
  </div>
</InteractivePanel>