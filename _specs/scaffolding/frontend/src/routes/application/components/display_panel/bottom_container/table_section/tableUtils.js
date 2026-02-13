import { displayAlert } from '@alert';
import { get } from 'svelte/store';
import { sheetData, selectedTable } from '@store';

export function copy(cellCoordinates, dataToDisplay) {
  const row = dataToDisplay.find(r => r.rowId === cellCoordinates.row);

  if (row) {
    const cellData = row.row.find(cell => cell.colId === cellCoordinates.col);
    if (cellData) {
      navigator.clipboard.writeText(cellData.value)
        .catch(err => {
          displayAlert('warning', 'Failed to copy text.');
        });
    }
  }
}

export function paste(cellCoordinates, dataToDisplay) {
  let pastePromise = navigator.clipboard.readText()
    .then(text => {
      const row = dataToDisplay.find(r => r.rowId === cellCoordinates.row);

      if (row) {
        const cellData = row.row.find(cell => cell.colId === cellCoordinates.col);
        if (cellData) {
          cellData.value = text;
          return dataToDisplay;
        }
      }
      return dataToDisplay; // Return original data if no cellData is found
    })
    .catch(err => {
      displayAlert('warning', 'Failed to paste text.');
      return dataToDisplay; // Return original data in case of error
    });
  return pastePromise;
}

export function getSortFunction({ column, direction }) {
  // Get column type from properties if available
  const sheet = get(sheetData);
  const currentTable = get(selectedTable);
  const properties = sheet[currentTable]?.properties || {};
  const columnType = properties[column] || 'general';

  return (a, b) => {
    if (direction === 'none') return 0;
  
    const aCellObj = a.row.find((cell) => cell.colId === column);
    const bCellObj = b.row.find((cell) => cell.colId === column);
    
    if (!aCellObj || !bCellObj) return 0;
    
    let aValue = aCellObj.value;
    let bValue = bCellObj.value;
    
    // Null values for us are all <N/A>
    if (aValue === "<N/A>" && bValue !== "<N/A>"){
      return direction === 'asc' ? -1 : 1; // For ascending: <N/A> first (-1), for descending: <N/A> last (1)
    }
    if (bValue === "<N/A>" && aValue !== "<N/A>") {
      return direction === 'asc' ? 1 : -1; // For ascending: <N/A> first (1), for descending: <N/A> last (-1)
    }
    if (aValue === "<N/A>" && bValue === "<N/A>") return 0;
    
    switch (columnType) {
      case 'currency':
        aValue = parseFloat(aValue.replace(/[$,£€]/g, ''));
        bValue = parseFloat(bValue.replace(/[$,£€]/g, ''));
        break;
        
      case 'percent':
        aValue = parseFloat(aValue.replace(/%/g, ''));
        bValue = parseFloat(bValue.replace(/%/g, ''));
        break;
        
      case 'whole':
      case 'decimal':
        aValue = parseFloat(aValue);
        bValue = parseFloat(bValue);
        break;
        
      case 'day':
      case 'year':
      case 'hour':
      case 'minute':
      case 'second':
        aValue = parseFloat(aValue.replace(/[^0-9.-]/g, ''));
        bValue = parseFloat(bValue.replace(/[^0-9.-]/g, ''));
        break;
        
      case 'date':
      case 'timestamp':
        try {
          aValue = new Date(aValue).getTime();
          bValue = new Date(bValue).getTime();
        } catch (e) {
          console.warn('Failed to parse date:', e);
        }
        break;
        
      case 'month':
        const monthMap = {
          january: 1, february: 2, march: 3, april: 4, may: 5, june: 6,
          july: 7, august: 8, september: 9, october: 10, november: 11, december: 12,
          jan: 1, feb: 2, mar: 3, apr: 4, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12
        };
        
        if (typeof aValue === 'string' && typeof bValue === 'string') {
          const aMonth = monthMap[aValue.toLowerCase()] || 0;
          const bMonth = monthMap[bValue.toLowerCase()] || 0;
          
          if (aMonth && bMonth) {
            aValue = aMonth;
            bValue = bMonth;
          }
        }
        break;

      default:
        if (typeof aValue === 'string' && typeof bValue === 'string') {
          aValue = aValue.toLowerCase();
          bValue = bValue.toLowerCase();
        }
    }
    
    if (isNaN(aValue) && !isNaN(bValue)) return 1;
    if (!isNaN(aValue) && isNaN(bValue)) return -1;
    if (isNaN(aValue) && isNaN(bValue)) {
      // If both are NaN after conversion, fall back to string comparison
      aValue = aCellObj.value.toString().toLowerCase();
      bValue = bCellObj.value.toString().toLowerCase();
    }
    
    if (aValue < bValue) return direction === 'asc' ? -1 : 1;
    if (aValue > bValue) return direction === 'asc' ? 1 : -1;
    return 0;
  };
}