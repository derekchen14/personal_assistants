import { writable, derived } from 'svelte/store';
import { browser } from '$app/environment';

// Element types registration
export const ELEMENT_TYPES = {
  TEXT_BLOCK: 'text_block',
  METRIC_CARD: 'metric_card',
  PLOTLY_CHART: 'plotly_chart',
  UPLOADED_FILE: 'uploaded_file'
};

// Default configurations for each element type
export const DEFAULT_ELEMENT_CONFIGS = {
  [ELEMENT_TYPES.TEXT_BLOCK]: {
    rowSpan: 1,
    colSpan: 2,
    content: {
      text: 'New text block',
      format: {
        bold: false,
        italic: false,
        underline: false
      }
    }
  },
  [ELEMENT_TYPES.METRIC_CARD]: {
    rowSpan: 1,
    colSpan: 1,
    content: {
      title: 'Metric',
      value: 0,
      changePercent: 0
    }
  },
  [ELEMENT_TYPES.PLOTLY_CHART]: {
    rowSpan: 3,
    colSpan: 3,
    content: {
      data: [],
      layout: {
        title: 'Chart Title',
        showlegend: true,
        autosize: true,
        margin: { l: 50, r: 50, b: 50, t: 50, pad: 4 }
      }
    }
  },
  [ELEMENT_TYPES.UPLOADED_FILE]: {
    rowSpan: 2,
    colSpan: 2,
    content: {
      imageSrc: '',
      altText: 'Uploaded image'
    }
  }
};

// Definition of the dashboard grid
export const GRID_CONFIG = {
  rows: 8,
  cols: 6
};

// Initialize dashboard elements from localStorage or empty array
const getInitialElements = () => {
  if (browser) {
    const storedElements = localStorage.getItem('dashboard-elements');
    if (storedElements) {
      try {
        return JSON.parse(storedElements);
      } catch (e) {
        console.error('Failed to parse stored dashboard elements:', e);
      }
    }
  }
  return [];
};

// Dashboard elements store
export const dashboardElements = writable(getInitialElements());

// Save dashboard elements to localStorage whenever they change
if (browser) {
  dashboardElements.subscribe(elements => {
    localStorage.setItem('dashboard-elements', JSON.stringify(elements));
  });
}

// Dashboard history for undo/redo functionality
export const dashboardHistory = writable({
  past: [],
  future: []
});

// Derived store for occupied grid positions
export const occupiedPositions = derived(dashboardElements, ($elements) => {
  const positions = new Set();
  
  $elements.forEach(element => {
    for (let r = 0; r < element.size.rows; r++) {
      for (let c = 0; c < element.size.cols; c++) {
        const pos = `${element.location.row + r},${element.location.col + c}`;
        positions.add(pos);
      }
    }
  });
  
  return positions;
});

// Derived store for empty cells
export const emptyCells = derived([occupiedPositions, dashboardElements], ([$occupied, $elements]) => {
  const empty = [];
  
  for (let row = 0; row < GRID_CONFIG.rows; row++) {
    for (let col = 0; col < GRID_CONFIG.cols; col++) {
      const pos = `${row},${col}`;
      if (!$occupied.has(pos)) {
        empty.push({ row, col });
      }
    }
  }
  
  return empty;
});

// Helper function to find first available space for an element of given size
export function findAvailableSpace(rows, cols) {
  let store;
  const unsubscribe = occupiedPositions.subscribe(occupied => {
    store = occupied;
  });
  unsubscribe();

  for (let row = 0; row < GRID_CONFIG.rows; row++) {
    for (let col = 0; col < GRID_CONFIG.cols; col++) {
      let canFit = true;
      
      // Check if all required cells are available
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          // Check if position is within grid bounds
          if (row + r >= GRID_CONFIG.rows || col + c >= GRID_CONFIG.cols) {
            canFit = false;
            break;
          }
          
          // Check if position is already occupied
          const pos = `${row + r},${col + c}`;
          if (store && store.has(pos)) {
            canFit = false;
            break;
          }
        }
        if (!canFit) break;
      }
      
      if (canFit) {
        return { row, col };
      }
    }
  }
  
  return null; // No space available
}

// Check if element can be placed at specified location
export function canPlaceElement(location, size, excludeElementId = null) {
  let store;
  let elements;
  
  const unsubOccupied = occupiedPositions.subscribe(occupied => {
    store = occupied;
  });
  unsubOccupied();
  
  const unsubElements = dashboardElements.subscribe(els => {
    elements = els;
  });
  unsubElements();
  
  // If location is outside grid bounds, return false
  if (location.row < 0 || location.col < 0 || 
      location.row + size.rows > GRID_CONFIG.rows || 
      location.col + size.cols > GRID_CONFIG.cols) {
    return false;
  }
  
  // Get the element being moved/resized
  const movingElement = excludeElementId ? elements.find(el => el.id === excludeElementId) : null;
  
  // Check each cell in the target area
  for (let r = 0; r < size.rows; r++) {
    for (let c = 0; c < size.cols; c++) {
      const pos = `${location.row + r},${location.col + c}`;
      
      // Skip if position is not occupied
      if (!store || !store.has(pos)) continue;
      
      // Find which element occupies this position
      const occupyingElement = elements.find(el => {
        for (let er = 0; er < el.size.rows; er++) {
          for (let ec = 0; ec < el.size.cols; ec++) {
            const elPos = `${el.location.row + er},${el.location.col + ec}`;
            if (elPos === pos) return true;
          }
        }
        return false;
      });
      
      // If position is occupied by a different element, placement is invalid
      if (occupyingElement && occupyingElement.id !== excludeElementId) {
        return false;
      }
    }
  }
  
  return true;
}

// Save current state to history before modification
function saveToHistory() {
  dashboardHistory.update(history => {
    let currentState;
    const unsubscribe = dashboardElements.subscribe(state => {
      currentState = [...state];
    });
    unsubscribe();
    
    return {
      past: [...history.past, currentState],
      future: []
    };
  });
}

// Add a new element to the dashboard
export function addElement(type, customContent = null, clickLocation = null) {
  saveToHistory();
  const defaultConfig = DEFAULT_ELEMENT_CONFIGS[type];
  if (!defaultConfig) {
    console.log("Unable to add element", type, ": defaultConfig is null");
    return false;
  }
  
  let elementLocation;
  
  // If click location is provided, try to place element there first
  if (clickLocation && typeof clickLocation.row === 'number' && typeof clickLocation.col === 'number') {
    // Try to fit element at click location at full size
    let fitSize = {
      rows: defaultConfig.rowSpan,
      cols: defaultConfig.colSpan
    };

    // If can't fit at full size, make it 1x1
    if (!canPlaceElement(clickLocation, fitSize)) {
      fitSize.rows = 1;
      fitSize.cols = 1;
    }

    elementLocation = clickLocation;
    defaultConfig.rowSpan = fitSize.rows;
    defaultConfig.colSpan = fitSize.cols;
  }
  
  // If no click location or can't place at click location, find next available space
  if (!elementLocation) {
    elementLocation = findAvailableSpace(defaultConfig.rowSpan, defaultConfig.colSpan);
    if (!elementLocation) {
      console.log("Unable to add element", type, ": elementLocation is null");
      return false;
    }
  }
  
  // Use custom content if provided, otherwise use default
  const elementContent = customContent || { ...defaultConfig.content };
  
  // Create new element with unique ID
  const newElement = {
    id: `${type}-${Date.now()}`,
    type,
    location: elementLocation,
    size: {
      rows: defaultConfig.rowSpan,
      cols: defaultConfig.colSpan
    },
    content: elementContent
  };
  
  // Add to dashboard
  dashboardElements.update(elements => [...elements, newElement]);
  return true;
}

// Update an element's content
export function updateElementContent(id, content) {
  saveToHistory();
  
  dashboardElements.update(elements => 
    elements.map(element => 
      element.id === id 
        ? { ...element, content: { ...element.content, ...content } }
        : element
    )
  );
}

// Move an element to a new location
export function moveElement(id, newLocation) {
  let element;
  let currentElements;
  
  // Get current element
  const unsubscribe = dashboardElements.subscribe(elements => {
    element = elements.find(el => el.id === id);
    currentElements = elements;
  });
  unsubscribe();
  
  if (!element) return false;
  
  // Check if new position is valid
  if (!canPlaceElement(newLocation, element.size, id)) return false;
  
  saveToHistory();
  
  // Update element location
  dashboardElements.update(elements =>
    elements.map(el =>
      el.id === id
        ? { ...el, location: newLocation }
        : el
    )
  );
  
  return true;
}

// Resize an element
export function resizeElement(id, newSize) {
  let element;
  
  // Get current element
  const unsubscribe = dashboardElements.subscribe(elements => {
    element = elements.find(el => el.id === id);
  });
  unsubscribe();
  
  if (!element) return false;
  
  // Check if new size is valid
  if (!canPlaceElement(element.location, newSize, id)) return false;
  
  saveToHistory();
  
  // Update element size
  dashboardElements.update(elements =>
    elements.map(el =>
      el.id === id
        ? { ...el, size: newSize }
        : el
    )
  );
  
  return true;
}

// Remove an element from the dashboard
export function removeElement(id) {
  saveToHistory();
  
  dashboardElements.update(elements =>
    elements.filter(element => element.id !== id)
  );
}

// Undo the last action
export function undo() {
  dashboardHistory.update(history => {
    if (history.past.length === 0) return history;
    
    let currentState;
    const unsubscribe = dashboardElements.subscribe(state => {
      currentState = [...state];
    });
    unsubscribe();
    
    const lastState = history.past[history.past.length - 1];
    const newPast = history.past.slice(0, history.past.length - 1);
    
    dashboardElements.set(lastState);
    
    return {
      past: newPast,
      future: [currentState, ...history.future]
    };
  });
}

// Redo the last undone action
export function redo() {
  dashboardHistory.update(history => {
    if (history.future.length === 0) return history;
    
    let currentState;
    const unsubscribe = dashboardElements.subscribe(state => {
      currentState = [...state];
    });
    unsubscribe();
    
    const nextState = history.future[0];
    const newFuture = history.future.slice(1);
    
    dashboardElements.set(nextState);
    
    return {
      past: [...history.past, currentState],
      future: newFuture
    };
  });
}

// Clear all elements from the dashboard
export function clearDashboard() {
  saveToHistory();
  dashboardElements.set([]);
}