<script lang="ts">
  import { writable, get } from 'svelte/store';
  import { serverUrl, receiveData, selectedTable, interactionView, selectTab, messageStore } from '@store';
  import { resetInteractions, pickedColumns, activatedItem, panelVariables, currentFlow } from '@store';
  import { displayAlert } from '@alert';
  import { securedFetch } from '$lib/apiUtils';

  import AddIcon from '@lib/icons/Add.svelte'
  import Constraint from '../dropdown/rowColConstraint.svelte';
  import InteractivePanel from './components/interactiveComp.svelte';
  export let target = 'row';

  let stage = '';
  let maxSize = 3;
  let titleText = '';
  let subtitleText = '';

  $: if ($interactionView.content && $resetInteractions) {
    const { flowType, content } = $interactionView;
    const selected = content['selected']
    currentFlow.set(flowType); // useful for demo purposes, otherwise set in receiveData
    maxSize = target === 'row' ? 5 : 4;

    if (selected.length === 0) {
      $activatedItem = 'items_0';
      $panelVariables['items'] = [{ tab: $selectedTable, col: '', ver: true }];
    } else {
      let activeTab = selected[0].tab;
      selectTab(activeTab);

      $panelVariables['items'] = selected.map(certificate => {
        pickedColumns.update(pc => {
          pc[`${certificate.tab}.${certificate.col}`] = { color: 'sky', count: 1 };
          return pc;
        });
        certificate['ver'] = true;
        return certificate
      });
    }
    $resetInteractions = false;
  }

  // If pickedColumns has changed, then check for 'N/A' colors and fill them
  $: if ($pickedColumns) {
    const pickedCols = get(pickedColumns);
    Object.entries(pickedCols).forEach(([tabColName, { color }]) => {
      if (color === 'N/A') {
        pickedColumns.update(pc => {
          pc[tabColName].color = 'sky';
          return pc;
        });
      }
    });
  }

  function createConstraint(table, column, verified=true) {
    let constraint = { tab: table, col: column, ver: verified };
    let tabColName = `${table}.${column}`;

    $activatedItem = `items_${$panelVariables['items'].length}`;
    panelVariables.update(vars => {
      vars['items'].push(constraint);
      return vars;
    });

    pickedColumns.update(pc => {
      pc[tabColName] = { color: 'sky', count: 1 };
      return pc;
    });
  }

  function addUserUtterance() {
    let columnNames = [];
    let currentTab = '';
    $panelVariables['items'].forEach(item => {
      columnNames.push(item['col']);
      currentTab = item['tab'];
    })
    const colString = columnNames.join(', ');

    let message = ''
    if (target == 'column') {
      message = `Merge the ${colString} columns together to form a new column in the ${currentTab} table.`;
    } else {
      message = `Please merge duplicate rows from ${currentTab} table based on the ${colString} columns.`;
    }

    messageStore.set({
      message: { type: 'text', content: message },
      userId: 'user', time: new Date()
    });
  }

  const handleCancel = () => {
    let flowName = target === 'column' ? 'Transform(merge)' : 'Clean(dedupe)';
    const payload = { flowType: flowName, stage: 'cancel', selected: [] };
    currentFlow.set(null);
    pickedColumns.set({});

    securedFetch(`${serverUrl}/interactions/merge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(response => response.json())
      .then(data => {receiveData(data)})
      .catch(error => console.log(error));
  }

  function handleFinish() {
    let flowName = target === 'column' ? 'Transform(merge)' : 'Clean(dedupe)';
    const payload = { flowType: flowName, stage: 'pick-tab-col', selected: [] };
    currentFlow.set(null);
    pickedColumns.set({});

    const filteredConstraints = $panelVariables['items'].filter(item => item.tab && item.col);
    const numEmptyConstraints = $panelVariables['items'].length - filteredConstraints.length;

    // Deal with problematic contraints first
    if (numEmptyConstraints > 0) {
      displayAlert('warning', `Some columns were left empty, so they were removed`);
      panelVariables['items'] = filteredConstraints;
    }
    if (filteredConstraints.length > 0) {
      payload.selected = filteredConstraints;
    } else {
      if (target === 'column') {
        displayAlert('warning', "Please select the columns to join together");
      } else {
        displayAlert('warning', "Please select a column to identify duplicates");
      }
      return; // Exit the current iteration if no valid columns were chosen
    }

    addUserUtterance()
    securedFetch(`${serverUrl}/interactions/merge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(response => response.json())
      .then(data => {receiveData(data)})
      .catch(error => console.log(error));
  }

  $: if ($pickedColumns) {
    let columnText = '';
    
    if (Object.keys($pickedColumns).length > 0) {
      const colNames = Object.keys($pickedColumns).map(pc => pc.split('.')[1]);
      if (colNames.length === 1) {
        columnText = `in the '${colNames[0]}' column`;
      } else if (colNames.length === 2) {
        columnText = `within the '${colNames[0]}' and '${colNames[1]}' columns`;
      } else {
        columnText = `within the '${colNames[0]}', '${colNames[1]}', and '${colNames[2]}' columns`;
      }
    }

    if (target === 'column') {
      titleText = 'Merge Columns';
      subtitleText = "Start by choosing the two or more columns you would like to merge together. On the next step, we will decide how to resolve merge conflicts.";
    } else {
      titleText = 'Remove Duplicates';
      subtitleText = `Choose the column(s) used to identify duplicate rows. Based on your selection, I will remove the duplicate when the values ${columnText} are exactly the same for both rows.`;
    }
  }

</script>

<InteractivePanel title={titleText} subtitle={subtitleText} customClass="mt-1 mb-3" index=0 total=3
  onReject={handleCancel} rejectLabel="Cancel"
  onAccept={handleFinish} acceptLabel="Finish">

  <div class="mx-auto inline-flex flex-shrink-0">
    {#each $panelVariables['items'] as constraint, pos}
      <Constraint {constraint} minSize={target === 'row' ? 0 : 2} position={pos}/>
    {/each}
    {#if $panelVariables['items'].length < maxSize}
      <button on:click={() => createConstraint('', '', true)} class="ml-8 mt-1.5 px-2 py-1 w-22 h-9 rounded
        bg-green-700/10 text-green-600 border-2 border-green-600 cursor-pointer">
        <AddIcon/> Add
      </button>
    {/if}
  </div>
</InteractivePanel>