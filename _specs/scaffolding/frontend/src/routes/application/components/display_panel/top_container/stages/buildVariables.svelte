<script lang="ts">
  import { writable, get } from 'svelte/store';
  import { serverUrl, receiveData, selectedTable, tableView, sheetData, interactionView } from '@store';
  import { resetInteractions, pickedColumns, activatedItem, panelVariables, currentFlow } from '@store';
  import { displayAlert } from '@alert';
  import { securedFetch } from '$lib/apiUtils';

  import AddIcon from '@lib/icons/Add.svelte'
  import Clause from '../dropdown/clause.svelte';
  import InteractivePanel from './components/interactiveComp.svelte';
  
  const Expression = { ADD: '+', SUBTRACT: '-', MULTIPLY: '*', DIVIDE: '/',
                       NOT: '!', INVERSE: 'inv', ABSOLUTE: 'abs', AND: '&', OR: '|' }
  const allColors = ['amber', 'sky', 'emerald', 'rose', 'violet', 'orange', 'green', 'cyan', 'fuchsia']
  const ordinals = ['first', 'second', 'third', 'fourth']

  let columnNames = []
  let rankedTabCols = []
  let panelMetadata = { name: '', alias: '', desc: '', variableNames: [] }

  const getFreeColor = () => {
    const usedColors = Object.values($pickedColumns).map(pc => pc.color);
    return allColors.find(color => !usedColors.includes(color));
  };

  $: columnNames = Object.keys($tableView[0]);

  // If pickedColumns has changed, then check for 'N/A' colors and fill them
  $: if ($pickedColumns) {
    const pickedCols = get(pickedColumns);
    Object.entries(pickedCols).forEach(([tabColName, { color }]) => {
      if (color === 'N/A') {
        pickedColumns.update(pc => {
          pc[tabColName].color = getFreeColor();
          return pc;
        });
      }
    });
  }

  $: if ($interactionView.content && $resetInteractions) {
    const { flowType, content } = $interactionView;
    let rankings = content['rankings'];
    let formula = content['formula'];

    panelMetadata = {name:formula.name, alias:formula.aliases[0],
                       desc:formula.description, variableNames:[]};
    rankedTabCols = rankings.map(rank => [rank.tab, rank.col]);

    let variables = {}
    for (let i=0; i < formula.expression.degree; i++) {
      const currentVar = formula.expression[ordinals[i]];

      if (currentVar.clauses.length === 0) {
        $activatedItem = `${currentVar.name}_0`;
        currentVar.clauses.push({ tab: '', col: '', rel: '+' });
      }

      variables[currentVar.name] = currentVar.clauses.map(clause => {
        const tabColName = `${clause.tab}.${clause.col}`
        pickedColumns.update(pc => {
          if (pc[tabColName]) {
            pc[tabColName].count += 1;
          } else {
            pc[tabColName] = { color: getFreeColor(), count: 1 };
          }
          return pc;
        });
        return { tab: clause.tab, col: clause.col, rel: clause.rel }
      });
      panelMetadata.variableNames.push(currentVar.name);
    }
    $panelVariables = variables;
    $resetInteractions = false;
  }

  function createClause(varName, table, column, relation='+') {
    let clause = { tab: table, col: column, rel: relation };
    let tabColName = `${table}.${column}`;

    panelVariables.update(vars => {
      vars[varName].push(clause);
      return vars;
    });

    pickedColumns.update(pc => {
      if (pc[tabColName]) {
        pc[tabColName].count += 1;
      } else {
        pc[tabColName] = { color: 'N/A', count: 1 };
      }
      return pc;
    });
    $activatedItem = `${varName}_${$panelVariables[varName].length - 1}`;
  }

  const handleCancel = () => {
    const metricPayload = { flowType: 'Select(analyze)', stage: 'build-variables', metric: 'cancel', variables: {} };
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
    const metricPayload = { flowType: 'Select(analyze)', stage: 'build-variables', variables: {} };
    metricPayload.metric = panelMetadata.name;
    currentFlow.set(null);

    Object.entries($panelVariables).forEach(([varName, clauses]) => {
      const filteredClauses = clauses.filter(clause => clause.tab && clause.col);
      const emptyClauses = clauses.length - filteredClauses.length;

      // Deal with problematic clauses first
      if (emptyClauses > 0) {
        displayAlert('warning', `Some sections for ${varName} are empty, so they were removed`);
        panelVariables.update(vars => { 
          vars[varName] = filteredClauses;  // Remove empty clauses
          return vars;
        });
      }
      if (filteredClauses.length === 0) {
        displayAlert('warning', `Please select a column for the ${varName} variable`);
        return; // Exit the current iteration if no valid clauses remain
      }

      // Prepare variable data for the payload by adding verification
      metricPayload.variables[varName] = filteredClauses.map(clause => {
        return { ...clause, ver: true };
      });
    });

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
  title="Metric Builder" subtitle="Activate a variable in the formula by simply clicking on it. Then choose the appropriate column for that variable by selecting from the dropdown menu or the spreadsheet."
  onReject={handleCancel} rejectLabel="Cancel"
  onAccept={handleFinish} acceptLabel="Finish"
  customClass="mb-2">

  <div class="mx-auto inline-flex flex-shrink-0 flex-row items-center">
    <div class="inline-flex flex-col items-center max-w-36">
      <span class="text-l text-center font-bold">{panelMetadata.alias}</span>
      <span class="text-l font-bold">({panelMetadata.name})</span>
    </div>
    <div class="text-2xl p-4">=</div>

    <div class="inline-flex flex-col items-center">
      {#each panelMetadata.variableNames as varName, index}

        {#if index > 0} <!-- Include a divider for all but the first variable -->
          <div class="w-full items-start"><div class="division border-t-2 border-gray-800 my-1"></div></div>
        {/if}

        <div class="variable font-medium inline-flex group ml-1 mb-1">
          {#each $panelVariables[varName] as clause, pos}
            <Clause {allColors} {clause} {rankedTabCols} varName={varName} position={pos}/>
          {/each}
          {#if $panelVariables[varName].length < 3}
            <button on:click={() => createClause(varName, '', '', '+')} class="ml-3 mt-1 pt-0.5 pl-2 pr-3 w-22
              bg-green-700/10 text-green-600 border-2 border-green-600 cursor-pointer rounded h-9
              transition-opacity duration-200 group-hover:opacity-100 opacity-0">
              <AddIcon/> Add 
            </button>
          {/if}
        </div>
      {/each}
    </div>

  </div>
</InteractivePanel>

<style>
  .division {
    width: calc(100% - 5rem);
  }
</style>

<!-- 
    {:else if $expressionRelation in oneLineBinaryExpressions}
    <div class="flex flex-row items-center">
      <span class="term-group vertical-term-group text-xl font-bold {$firstVariable.length === 3 ? 'term-full' : ''} ">
        {#each $firstVariable as term, i}
          <Variable colors={colors} setColor={setColor} i={i} term={term} showDelete={$firstVariable.length > 1} deleteColumn={() => { deleteColumn(firstVariable, i)}} vertical={true} defaultLabel={$interactionView.content.expression.first.name} />
        {/each}
        <span>
          <button on:click={() => {createClause(firstVariable)}}
            class={`m-1 px-3 font-medium text-green-700 bg-green-700/10 border border-green-700 cursor-pointer rounded similar-terms-button relative add-button invisible`}
            ><Plus /> Add</button>
        </span>
      </span>

      <span>
        {#if $expressionRelation == '+'}
          <Plus />
        {:else if $expressionRelation == '-'}
          <Minus />
        {:else if $expressionRelation == '*'}
          <Multiply />
        {/if}
      </span>
      
      <span class="term-group vertical-term-group text-xl font-bold {$secondVariable.length === 3 ? 'term-full' : ''} ">
        {#each $secondVariable as term, i}
          <Variable colors={colors} setColor={setColor} i={i} term={term} showDelete={$secondVariable.length > 1} deleteColumn={() => { deleteColumn(secondVariable, i)}} vertical={true} defaultLabel={$interactionView.content.expression.second.name} />
        {/each}
        <span>
          <button on:click={() => {createClause(secondVariable)}}
            class={`m-1 px-3 font-medium text-green-700 bg-green-700/10 border border-green-700 cursor-pointer rounded similar-terms-button relative add-button invisible`}
            ><Plus /> Add</button>
        </span>
      </span>
    </div>

<style>
  .vertical-term-group {
    display: flex;
    flex-direction: column;
  }
</style>
-->