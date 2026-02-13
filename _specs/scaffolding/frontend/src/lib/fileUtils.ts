import { displayAlert } from '@alert';
import Papa from 'papaparse';

/* Prepares CSV for Pandas consumption by pandas:
  1. Quoting values with commas
  2. Replace problematic characters that may cause line breaks
     - new lines and carriage returns
     - tabs and form feeds
     - zero-width spaces and other invisible unicode spaces
  3. Trimming whitespace
  4. Extending the first row to match the number of columns in the longest row    */
export async function preprocessCSV(file) {
  const content = await file.text();
  const parseResult = Papa.parse(content, {
    skipEmptyLines: 'greedy', comments: '#', quotes: true,
  });
  const maxColumns = parseResult.data.reduce((max, row) => Math.max(max, row.length), 0);

  const parsedData = parseResult.data.map((row, rowIndex) => {
    const processedRow = row.map(cell => {
      // Handle string conversion first
      let value = typeof cell === 'string' ? cell : (cell?.toString() || '');
      // Replace problematic characters that may cause line breaks
      value = value.replace(/[\r\n]+/g, ' ').replace(/[\v\f\t]+/g, ' ').replace(/[\u200B-\u200D\uFEFF\u00A0]+/g, '')
      // Escape double quotes and trim whitespace
      value = value.replace(/"/g, '""').trim();
      // Quote values that contain commas or are currency values
      if (value.includes(',') || /^\$[\d,]+\.\d{2}$/.test(value)) {
        return `"${value}"`;
      }
      return value;
    });

    // Extend the first row to match the max number of columns
    if (rowIndex === 0 && processedRow.length < maxColumns) {
      while (processedRow.length < maxColumns) {
        processedRow.push('0');  // skip_preamble helper stops on digit-based headers
      }
    }
    return processedRow.join(',');
  }).join('\n');

  return parsedData;
}

/* Inputs: parsedData (string), maxFileSize (number)
Outputs: trimmedData (string) - the trimmed CSV data, not a File object yet */
export async function trimLargeCSV(parsedData, maxFileSize) {
  let trimmedData = parsedData;
  let dropThreshold = 0.16;
  let numColsRemoved = 0;
  let currentSize = maxFileSize + 1;
  let trimMessage = '';
  
  // Convert to array of arrays for easier manipulation
  const csvData = parsedData.split('\n').map(row => row.split(','));
  const columnCount = csvData[0].length;  // Since we extended the header, it will be the max
  const nullFrequencies = calculateNullRatio(csvData, columnCount);

  // Drop columns and rows until the file size is within the limit
  while (currentSize > maxFileSize) {
    
    if (dropThreshold > 0.2) {
      // threshold is over 20% so we start dropping rows instead
      const trimmedRows = trimmedData.split('\n');
      const numRows = trimmedRows.length;
      // drop the bottom 1% of rows
      const rowsToDrop = Math.floor(numRows * 0.01);      

      trimMessage += `Also removing ${rowsToDrop} rows.`;
      trimmedData = trimmedRows.slice(0, numRows - rowsToDrop).join('\n');
    } else {
      // remove columns that are mostly empty
      const columnsToKeep = [];   // Re-compile every round to make sure indexes stay correct
      for (let idx = 0; idx < columnCount; idx++) {
        const keepRatio = 1 - dropThreshold;
        if (nullFrequencies[idx] < keepRatio) {
          columnsToKeep.push(idx);
        } else {
          numColsRemoved++;
        }
      }

      // Create a new dataset with only the kept columns
      trimMessage = `Trimming down to ${columnsToKeep.length} columns after removing ${numColsRemoved} columns.`;
      trimmedData = csvData.map(row =>
        columnsToKeep.map(colIndex => row[colIndex] || '').join(',')
      ).join('\n');
    }

    displayAlert('warning',
      [ `File size limit is ${maxFileSize} MB.`, trimMessage, 'Upgrading to Pro will allow larger files.',].join(' ')
    );

    // Update variables for the next iteration if needed
    currentSize = new Blob([trimmedData]).size / (1024 * 1024); // Size in MB
    dropThreshold *= 2;
  }
  return trimmedData
}

/* Inputs: csvData (Array of arrays), columnCount (number)
Outputs: nullFrequencies (Array) - each element represents the percentage of null-like values in a column */
function calculateNullRatio(csvData, columnCount) {
  const numRows = csvData.length;
  const nullEquivalents = ['', '0', '""', "''", 'null', 'NaN', 'undefined', 'N/A'];
  
  // Track the number of nulls in each column
  const columnNulls = new Array(columnCount).fill(0);
  csvData.forEach(row => {
    row.forEach((cell, colIndex) => {
      // Count empty, zero, or quoted empty values as nulls
      if (!cell || nullEquivalents.includes(cell)) {
        columnNulls[colIndex]++;
      }
    });
  });

  // Calculate the percentage of nulls in each column
  const nullFrequencies = new Array(columnCount).fill(0);
  columnNulls.forEach((count, colIndex) => {
    nullFrequencies[colIndex] = count / numRows;
  });

  return nullFrequencies;
}

export function extensionToMIME(extension: string): string {
  switch (extension) {
    case 'csv':
      return 'text/csv';
    case 'tsv':
      return 'text/tab-separated-values';
    case 'xlsx':
      return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
    case 'ods':
      return 'application/vnd.oasis.opendocument.spreadsheet';
    default:
      throw new Error(`Invalid file extension ${extension}.`);
  }
}

export function prepareTableName(segments: string[]): string {
  let tabName = segments.join(' ')
  // drop keywords of 'sample', 'example', 'final', 'test', or 'data', which can confuse LLMs
  tabName = tabName.replace(/\b(sample|example|final|test|data)\b/g, '');
  // remove special characters from table name, allow only alphanumeric and underscores
  tabName = tabName.replace(/[^a-zA-Z0-9_ ]/g, '');
  // avoid spaces in table name, convert to underscores
  tabName = tabName.replace(/ +/g, ' ').trim().replace(/ /g, '_');
  // limit table name length to 32
  tabName = tabName.slice(0, 32);

  if (tabName.length === 0) {
    tabName = 'my_table';
  }
  return tabName;
}