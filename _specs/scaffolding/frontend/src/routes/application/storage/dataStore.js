import { displayAlert } from '@alert';
import { writable, get, derived } from 'svelte/store';
import { serverUrl, messageStore, lastAction, displayLayout, activeConnector, hasSuggestion, conversationId, utteranceHistory } from './store';
import { securedFetch } from '$lib/apiUtils';
import { defaultSheets } from '$lib/data';
import { logger } from '$lib/logger';
import { goto } from '$app/navigation';

export const selectedSpreadsheet = writable(null);
export const selectedTable = writable('');
export const sheetData = writable({});  // keys are tab names, values are the actual data
export const tempData = writable(null);
export const currentFlow = writable(null);
export const currentStage = writable(null);

export const chatActive = writable(false); // activated when data is successfully loaded
export const saveStatus = writable('none'); // none, active, done, error
export const showResetModal = writable(false);

export const managerView = writable(false);
export const exportView = writable(false);
export const tableView = writable(null);
export const tableType = writable('direct');  // [direct, derived, dynamic, decision]
export const tabSwitchTrigger = writable(0);
export const fileSelectorView = writable(false);

export const tableStore = derived([tableView, tableType], ([$tableView, $tableType]) => {
  return { tableData: $tableView, tableType: $tableType };
});

export const availableSheets = writable(JSON.parse(defaultSheets));
export const resetTrigger = writable(0);

let saveTimer;
let interactionHistory = [];

export async function saveEdits() {
  if (!interactionHistory.length) return; // Early exit if there are no interactions to save
  saveStatus.set('active');
  const currentTable = get(selectedTable)

  const response = await securedFetch(`${serverUrl}/interactions/edit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ updates: interactionHistory, tab_name: currentTable }),
  });

  if (response.ok) {
    interactionHistory = [];  // Clear interactionHistory since they are now successfully saved
    saveStatus.set('done');
    resetSheetData(currentTable);
  } else {
    const errorData = await response.json();
    console.error(`Error updating changes: ${errorData.detail}`);
    saveStatus.set('error');
  }

  setTimeout(() => {
    saveStatus.set('none');
  }, 5000);
}

export function pushEdit(interaction) {
  interactionHistory.push(interaction);
  // Clear any existing timer, then set a new one for 1 minute
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveEdits, 60000);
}
export function popEdit() {
  if (!interactionHistory.length) {
    return null; // Return null or an empty object if there is no history
  }
  return interactionHistory.pop(); // Return and remove the last action
}

export function initializeSheetData(tableNames) {
  tableNames.forEach(tabName => {
    resetSheetData(tabName);
  });
  tempData.set({ rows: [], name: '' });
}

// Create a new function for initializing a tab structure
export function initializeTabStructure(properties = {}) {
  return {
    rows: [],            // holds the actual data, each row is a dictionary and dict keys are the column names
    lastFetchedRow: 0,   
    hasMoreData: true,   
    anchorPoints: [],
    visibility: new Map(), // holds the row ids that are currently visible in the table view
    properties: properties // holds schema information for the table
  };
}

function resetSheetData(tabName) {
  // Reset sheetData so we don't use cache next time
  sheetData.update(currentSheet => {
    currentSheet[tabName] = initializeTabStructure({});
    return currentSheet;
  });
}

export function pickTabRows(row_ids) {
  // pick a subset of rows from current table to display
  const sheet = get(sheetData);
  const tabName = get(selectedTable);
  const pickedRows = row_ids.map(id => sheet[tabName].rows[id]);
  tableView.set(pickedRows);
}


export function manageDerivedData(frame) {
  // derived tables are always a single table
  const tabName = frame.tabs[0];
  tempData.set({ rows: JSON.parse(frame.data), name: tabName });

  selectedSpreadsheet.update(spreadsheet => {
    const existingIndex = spreadsheet.tabNames.findIndex(name => name.startsWith('('));
    if (existingIndex >= 0) {
      spreadsheet.tabNames[existingIndex] = tabName;
    } else {
      spreadsheet.tabNames.push(tabName);
    }
    return spreadsheet;
  });

  selectedTable.set(tabName);
  tableType.set('derived');
}

export function manageDirectData(definition) {
  const tabNames = definition.tabs;
  const numRows = definition.rows;
  const colNames = definition.cols;
  const tabControl = definition.control;
  const mainTable = tabNames[0];

  // if reset signal, then clear the cache so that we pull new data from the server
  if (definition.reset) { tabNames.forEach(tabName => resetSheetData(tabName)); }
  if (tabControl['drop'] != '') { dropTable(tabControl['drop']); }
  if (tabControl['create'] != '') { createTable(tabControl['create']); }
  if (tabControl['rename'] != '') { renameTable(tabControl['rename'], mainTable); }
  const sheet = get(sheetData);

  tabSwitchTrigger.update(n => n + 1);
  selectedTable.set(mainTable);

  if (sheet[mainTable].lastFetchedRow === 0) {
    fetchData(mainTable, numRows);
  } else {
    // pull from existing sheetData
    const rawData = [];
    for (let i = 0; i < numRows; i++) {
      let rowDict = {};
      colNames.forEach(col => { rowDict[col] = sheet[mainTable].rows[i][col]; });
      rawData.push(rowDict);
    }
    populateSheetData(mainTable, rawData, 0);
  }
}

export function manageDecisionData(definition) {
  const tabNames = definition.tabs;
  tableType.set('decision');
}

export async function manageDynamicData(definition) {
  if (definition.conflicts) {
    // multiple columns may be involved in the conflict
    dynamicConflictTable(definition);
  } else if (definition.issues) {
    // only a single column is involved in the issue
    dynamicIssueTable(definition);
  }
}

async function dynamicConflictTable(definition) {
  const numRows = definition.conflicts;
  const tabNames = definition.tabs;        // tabNames is a list of up to two tab names
  const anchorRows = definition.rows;
  const anchorColumns = definition.cols;    // anchorColumns is a list of column name lists

  tabSwitchTrigger.update(n => n + 1);
  const sheet = get(sheetData);

  // If there is only one tab, then pull both sides
  if (tabNames.length === 1) {
    let tabName = tabNames[0];
    let currentColumns = anchorColumns[0];
    let currentRows = anchorRows.reduce((rows, val) => rows.concat(val), []);

    selectedTable.set(tabName);
    if (numRows > sheet[tabName].lastFetchedRow) {
      await fetchData(tabName, numRows);
    }
    sheetData.update(currentSheet => {
      currentSheet[tabName].anchorPoints = currentRows.flatMap(anchorRow =>
        currentColumns.map(anchorCol => [anchorCol, anchorRow])
      );
      currentSheet[tabName].rows.forEach((_, idx) => {
        currentSheet[tabName].visibility.set(idx, currentRows.includes(idx));
      });
      return currentSheet;
    });
  } else {
    // for (let i = 0; i < tabNames.length; i++) {
    //  let dynamicTabName = '(' + tabNames[i] + ')';
    for (const [i, tabName] of tabNames.entries()) {
      let currentColumns = anchorColumns[i];
      let currentRows = anchorRows[i];

      selectedTable.set(tabName);
      if (numRows > sheet[tabName].lastFetchedRow) {
        await fetchData(tabName, numRows);
      }

      sheetData.update(currentSheet => {
        currentSheet[tabName].anchorPoints = currentRows.flatMap(anchorRow =>
          currentColumns.map(anchorCol => [anchorCol, anchorRow])
        );
        currentSheet[tabName].rows.forEach((_, idx) => {
          currentSheet[tabName].visibility.set(idx, currentRows.includes(idx));
        });
        return currentSheet;
      });
    };
  }
  tableType.set('dynamic');
}

async function dynamicIssueTable(definition) {
  const tabName = definition.tabs[0];   // tabName is a single table name extracted from a list
  const anchorRows = definition.rows;   // anchorRows is a list of row ids
  const anchorCol = definition.cols;    // anchorCol is a single column string
  const issueMap = definition.issues;   // a dictionary of row ids to issue values
  const numRows = Math.max(...anchorRows) + 1;

  tabSwitchTrigger.update(n => n + 1);
  selectedTable.set(tabName);

  const sheet = get(sheetData);
  if (numRows > sheet[tabName].lastFetchedRow) {
    await fetchData(tabName, numRows);
  }
  sheetData.update(currentSheet => {
    currentSheet[tabName].anchorPoints = anchorRows.map(anchorRow => [anchorCol, anchorRow]);
    currentSheet[tabName].rows.forEach((_, idx) => {
      currentSheet[tabName].visibility.set(idx, anchorRows.includes(idx));
    });
    Object.entries(issueMap).forEach(([rowId, rowValue]) => {
      currentSheet[tabName].rows[rowId][anchorCol] = rowValue;
    });
    return currentSheet;
  });
  tableType.set('dynamic');
}

function dropTable(tabName) {
  // remove the tabName from the selectedSpreadsheet
  selectedSpreadsheet.update(spreadsheet => {
    const dropIndex = spreadsheet.tabNames.findIndex(name => name === tabName);
    if (dropIndex >= 0) {
      spreadsheet.tabNames.splice(dropIndex, 1);
    }
    return spreadsheet;
  });
}

function createTable(tabName) {
  // add the new tabName to the selectedSpreadsheet
  selectedSpreadsheet.update(spreadsheet => {
    const tempIndex = spreadsheet.tabNames.findIndex(name => name.startsWith('('));
    if (tempIndex >= 0) {
      // remove any derived tables from tabNames
      spreadsheet.tabNames.splice(tempIndex, 1);
    }
    if (!spreadsheet.tabNames.includes(tabName)) {
      spreadsheet.tabNames.push(tabName);
    }
    return spreadsheet;
  });
}

function renameTable(oldTabName, newTabName) {
  // rename the table name in the selectedSpreadsheet
  selectedSpreadsheet.update(spreadsheet => {
    const renameIndex = spreadsheet.tabNames.findIndex(name => name === oldTabName);
    if (renameIndex >= 0) {
      spreadsheet.tabNames[renameIndex] = newTabName;
    }
    return spreadsheet;
  });
}

export function populateSheetData(tabName, data, limit=512) {
  // Check if data is just a single empty row
  const isEmptyResponse = data.length === 1 &&
    data[0] &&
    Object.values(data[0]).every(value => value === '');
  
  if (isEmptyResponse) {
    // If we received just an empty row, don't add it and mark as no more data
    sheetData.update(currentSheet => {
      const tabData = currentSheet[tabName];
      tabData.hasMoreData = false;
      return currentSheet;
    });
  } else {
    // updates sheetData for a given tab with new data
    const beforeUpdate = get(sheetData);
    const currentProperties = beforeUpdate[tabName]?.properties || {};
    
    sheetData.update(currentSheet => {
      const tabData = currentSheet[tabName];
      tabData.rows.push(...data);
      tabData.lastFetchedRow += data.length;
      
      // Make sure we preserve the properties that might have been set earlier
      if (Object.keys(currentProperties).length > 0 && Object.keys(tabData.properties).length === 0) {
        tabData.properties = currentProperties;
      }
      
      // Initialize visibility state for new rows
      data.forEach((_, index) => {
        tabData.visibility.set(tabData.lastFetchedRow - data.length + index, true);
      });

      // If we received less than the limit, mark as no more data
      if (data.length < limit) {
        tabData.hasMoreData = false;
      }
      return currentSheet;
    });
    tableType.set('direct');
  }
}

export async function fetchData(tabName, rowEnd= -1) {
  const sheet = get(sheetData);
  const rowStart = sheet[tabName] ? sheet[tabName].lastFetchedRow : 0;
  if (rowEnd < 0) {
    rowEnd = rowStart < 512 ? 512 : Math.ceil((rowStart + 1) / 1024) * 1024;
  }

  const url = `${serverUrl}/sheets/fetch?tab_name=${tabName}&row_start=${rowStart}&row_end=${rowEnd}`;
  const response = await securedFetch(url, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' }
  });

  if (response.ok) {
    const tableData = await response.json();
    populateSheetData(tabName, tableData.content, rowEnd - rowStart);
  } else {
    const errorData = await response.json();
    console.error(`Error fetching direct table ${tabName}: ${errorData.detail}`);
  }
}

export async function selectSheet(spreadsheet) {
  chatActive.set(false);  // Reset chat to inactive so we can show the loading screen
  displayLayout.set('bottom');

  selectedSpreadsheet.set(spreadsheet);
  const response = await securedFetch(`${serverUrl}/sheets/select`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(spreadsheet),
  });

  if (response.ok) {
    let tableData = await response.json();
    let currentTab = spreadsheet.tabNames[0];
    
    initializeSheetData(spreadsheet.tabNames);
    populateSheetData(currentTab, tableData.content);

    selectedTable.set(currentTab);
    chatActive.set(true);
    managerView.set(false);
    displayAlert('success', `The ${spreadsheet.ssName} data has been selected.`);
  } else {
    const errorData = await response.json();
    throw new Error(`HTTP error (status ${response.status}): ${errorData.detail}`);
  }
}

export async function selectTab(tabName) {
  if (get(selectedTable) === tabName) return;
  tabSwitchTrigger.update(n => n + 1);
  await saveEdits();
  selectedTable.set(tabName);
  const flow = get(currentFlow);

  if (tabName.startsWith('(') && tabName.endsWith(')')) {
    selectDerivedTable(tabName);
  } else if ( flow && ['Select(analyze)', 'Transform(merge)', 'Transform(integrate)'].includes(flow) ) {
    selectDecisionTable(tabName);
  } else {
    selectDirectTable(tabName);
  }
}

function selectDerivedTable(tabName) {
  const temp = get(tempData);
  if (temp.name === tabName) {
    tableType.set('derived');
    tableView.set(temp.rows);
  } else {
    console.error(`No data found for derived table: ${tabName}`);
  }
}

async function selectDecisionTable(tabName) {
  const sheet = get(sheetData);
  if (sheet[tabName] && sheet[tabName].lastFetchedRow > 0) {
    // Use existing data we already have
    tableView.set(sheet[tabName].rows);
  } else {
    // Otherwise, get the first 256 rows
    const url = `${serverUrl}/sheets/fetch?tab_name=${tabName}&row_start=0&row_end=256`;
    const response = await securedFetch(url, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });
    // update sheetData with the new data
    if (response.ok) {
      const tableData = await response.json();
      populateSheetData(tabName, tableData.content)
    } else {
      const errorData = await response.json();
      console.error(`Error fetching decision table ${tabName}: ${errorData.detail}`);
    }
  }
  tableType.set('decision');
}

async function selectDirectTable(tabName) {
  const sheet = get(sheetData);
  if (sheet[tabName] && sheet[tabName].lastFetchedRow > 0) {
    // Just use the existing data
    tableView.set(sheet[tabName].rows);
    tableType.set('direct');
  } else {
    fetchData(tabName);
  }
}

export async function resetChat(enableNotification = true) {
  // Reset all the stores to their initial state
  showResetModal.set(false);
  resetTrigger.update(n => n + 1);
  availableSheets.set(JSON.parse(defaultSheets));
  displayLayout.set('split');
  activeConnector.set('upload')

  selectedSpreadsheet.set(null);
  selectedTable.set('');
  sheetData.set({});
  tempData.set(null);

  chatActive.set(false);
  utteranceHistory.set([]);
  conversationId.set(null);
  hasSuggestion.set(false);
  saveStatus.set('none');
  tableType.set('direct');
  messageStore.set(null);
  lastAction.set(null);

  managerView.set(false);
  exportView.set(false);
  tableView.set(null);
  currentFlow.set(null);
  currentStage.set(null);

  logger.resetConversationID();

  // TODO: save any pending edits before resetting when we start persisting history
  const response = await securedFetch(`${serverUrl}/user/reset`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });

  if (response.ok) {
    goto('/application');
    if (enableNotification) {
      displayAlert('success', 'The entire conversation has been reset.');
    }
  } else {
    const errorData = await response.json();
    throw new Error(`HTTP error (status ${response.status}): ${errorData.detail}`);
  }
}

export function updateTabProperties(tabName, schema) {
  sheetData.update(data => {
    if (!data[tabName]) {
      data[tabName] = initializeTabStructure(schema);
    } else {
      data[tabName].properties = schema;
    }
    return data;
  });
}
