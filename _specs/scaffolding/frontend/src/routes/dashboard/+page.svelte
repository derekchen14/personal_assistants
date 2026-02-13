<script lang="ts">
  import { onMount } from 'svelte';
  import { browser } from '$app/environment';
  import { goto } from '$app/navigation';
  import { checkAuthentication } from '../../lib/apiUtils';
  import ElementFactory from './components/elementFactory.svelte';
  import ElementSelectionMenu from './components/elementSelectionMenu.svelte';
  import { updateElementContent } from './stores/dashboard';
  
  import {
    dashboardElements,
    GRID_CONFIG,
    emptyCells,
    addElement,
    moveElement,
    resizeElement,
    removeElement,
    undo,
    redo,
    clearDashboard,
    canPlaceElement
  } from './stores/dashboard';
  
  // Grid configuration
  const { rows, cols } = GRID_CONFIG;
  // State variables
  let showElementMenu = false;
  let menuPosition = { x: 0, y: 0 };
  let targetCell = { row: 0, col: 0 };
  let isDragging = false;
  let draggedElementId = null;
  let draggedElement = null;
  let dragOverCell = null;
  let isInvalidPlacement = false;
  let dragOffset = { row: 0, col: 0 };
  
  // Add these new state variables for resize functionality
  let isResizing = false;
  let resizingElementId = null;
  let resizingElement = null;
  let resizeDirection = null;
  let resizeStartX = 0;
  let resizeStartY = 0;
  let initialSize = { rows: 0, cols: 0 };
  
  // Dashboard title state variables
  let dashboardTitle = "Dashboard";
  let editingTitle = false;
  let titleInputRef;
  
  // Open element selection menu
  function openElementMenu(row, col, event) {
    // Determine position relative to grid
    menuPosition = {
      x: event.clientX,
      y: event.clientY
    };
    
    targetCell = { row, col };
    showElementMenu = true;
  }
  
  // Close element selection menu
  function closeElementMenu() {
    showElementMenu = false;
  }
  
  // Handle element selection
  function handleElementSelect(event) {
    const type = event.detail.type;
    closeElementMenu();
    addElement(type, null, targetCell);
  }
  
  // Start dragging an element
  function handleDragStart(event, element) {
    isDragging = true;
    draggedElementId = element.id;
    draggedElement = element;
    
    // Calculate which cell within the element was clicked
    const cellWidth = document.querySelector('.dashboard-grid').clientWidth / cols;
    const cellHeight = document.querySelector('.dashboard-grid').clientHeight / rows;
    
    // Get the element's position relative to the grid
    const elementRect = event.currentTarget.getBoundingClientRect();
    
    // Calculate the clicked position relative to the element's top-left
    const relativeX = event.clientX - elementRect.left;
    const relativeY = event.clientY - elementRect.top;
    
    // Convert to grid cells
    dragOffset = {
      row: Math.floor(relativeY / cellHeight),
      col: Math.floor(relativeX / cellWidth)
    };
    
    // Set data transfer for dragging
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', element.id);
  }
  
  // Handle drag over cell
  function handleDragOver(event, row, col) {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
    
    if (!draggedElement) return;
    
    // Adjust the target position based on drag offset
    const targetRow = row - dragOffset.row;
    const targetCol = col - dragOffset.col;
    
    // Calculate all cells that would be covered
    const coveredCells = [];
    for (let r = 0; r < draggedElement.size.rows; r++) {
      for (let c = 0; c < draggedElement.size.cols; c++) {
        coveredCells.push({
          row: targetRow + r,
          col: targetCol + c
        });
      }
    }
    
    // Check if placement is valid
    isInvalidPlacement = !canPlaceElement({ row: targetRow, col: targetCol }, draggedElement.size, draggedElementId);
    
    // Update drag over cells
    dragOverCell = coveredCells;
  }
  
  // Handle element drop
  function handleDrop(event, row, col) {
    event.preventDefault();
    
    const elementId = event.dataTransfer.getData('text/plain');
    if (!elementId || !draggedElement) return;
    
    // Adjust the target position based on drag offset
    const targetRow = row - dragOffset.row;
    const targetCol = col - dragOffset.col;
    
    // Move the element to the adjusted position
    moveElement(elementId, { row: targetRow, col: targetCol });
    
    // Reset dragging state
    isDragging = false;
    draggedElementId = null;
    draggedElement = null;
    dragOverCell = null;
    dragOffset = { row: 0, col: 0 };
  }
  
  // Handle drag end
  function handleDragEnd() {
    isDragging = false;
    draggedElementId = null;
    draggedElement = null;
    dragOverCell = null;
    isInvalidPlacement = false;
    dragOffset = { row: 0, col: 0 };
  }
  
  // Start resizing an element
  function handleResizeStart(event, element, direction) {
    event.preventDefault();
    event.stopPropagation();
    
    isResizing = true;
    resizingElementId = element.id;
    resizingElement = element;
    resizeDirection = direction;
    
    // Record starting position and size
    resizeStartX = event.clientX;
    resizeStartY = event.clientY;
    initialSize = { ...element.size };
    
    // Add event listeners for mousemove and mouseup
    window.addEventListener('mousemove', handleResizeMove);
    window.addEventListener('mouseup', handleResizeEnd);
  }
  
  // Calculate new size based on mouse movement
  function calculateNewSize(event) {
    const cellWidth = document.querySelector('.dashboard-grid').clientWidth / cols;
    const cellHeight = document.querySelector('.dashboard-grid').clientHeight / rows;
    
    const deltaX = Math.round((event.clientX - resizeStartX) / cellWidth);
    const deltaY = Math.round((event.clientY - resizeStartY) / cellHeight);
    
    return {
      cols: resizeDirection.includes('e') ? Math.max(1, initialSize.cols + deltaX) : initialSize.cols,
      rows: resizeDirection.includes('s') ? Math.max(1, initialSize.rows + deltaY) : initialSize.rows
    };
  }
  
  // Check if the new size is different from current size
  function hasSizeChanged(newSize) {
    return newSize.cols !== resizingElement.size.cols || 
           newSize.rows !== resizingElement.size.rows;
  }
  
  // Check if the new size matches the original size
  function isReturningToOriginalSize(newSize) {
    return newSize.cols === resizingElement.size.cols && 
           newSize.rows === resizingElement.size.rows;
  }
  
  // Handle resize during mouse movement
  function handleResizeMove(event) {
    if (!isResizing || !resizingElement) return;
    
    const newSize = calculateNewSize(event);
    resizeElement(resizingElementId, newSize);
  }
  
  // End resizing
  function handleResizeEnd() {
    isResizing = false;
    resizingElementId = null;
    resizingElement = null;
    resizeDirection = null;
    
    // Remove event listeners
    window.removeEventListener('mousemove', handleResizeMove);
    window.removeEventListener('mouseup', handleResizeEnd);
  }
  
  // Dashboard title editing functions
  function startEditingTitle() {
    editingTitle = true;
    // Focus the input field after the DOM updates
    setTimeout(() => {
      if (titleInputRef) {
        titleInputRef.focus();
        titleInputRef.select();
      }
    }, 0);
  }
  
  function saveTitle() {
    // Trim the title and ensure it's not empty
    dashboardTitle = dashboardTitle.trim() || "Dashboard";
    editingTitle = false;
    
    // Save title to localStorage
    if (browser) {
      localStorage.setItem('dashboardTitle', dashboardTitle);
    }
  }
  
  function handleTitleKeydown(event) {
    if (event.key === 'Enter') {
      saveTitle();
    } else if (event.key === 'Escape') {
      editingTitle = false;
    }
  }
  
  // Generate grid cells for visualization
  $: gridCells = Array.from({ length: rows * cols }, (_, index) => {
    const row = Math.floor(index / cols);
    const col = index % cols;
    return { row, col };
  });
  
  // Check if a cell is empty (not occupied by any element)
  $: isEmptyCell = (row, col) => {
    if (isDragging && draggedElement) {
      // Release cells occupied by dragged element
      for (let r = 0; r < draggedElement.size.rows; r++) {
        for (let c = 0; c < draggedElement.size.cols; c++) {
          if (draggedElement.location.row + r === row && 
              draggedElement.location.col + c === col) {
            return true;
          }
        }
      }
    }
    
    // Check normal empty cells
    return $emptyCells.some(cell => cell.row === row && cell.col === col);
  };
  
  // Check if a cell is being dragged over
  $: isDragOverCell = (row, col) => {
    if (!dragOverCell) return false;
    return dragOverCell.some(cell => cell.row === row && cell.col === col);
  };
  
  // Initialize on mount
  onMount(async () => {
    try {
      // Check if user is authenticated using the utility function and properly await it
      const isAuthenticated = await checkAuthentication();
      
      if (!isAuthenticated) {
        console.log('User not authenticated, redirecting to login page');
        goto('/login');
        return;
      }
      
      // Load dashboard title from localStorage
      if (browser) {
        const savedTitle = localStorage.getItem('dashboardTitle');
        if (savedTitle) {
          dashboardTitle = savedTitle;
        }
      }
    } catch (error) {
      console.error('Authentication error:', error);
      goto('/login');
    }
  });

  function update_handler(id, content) {
    updateElementContent(id, content);
  }
</script>

<svelte:head>
  <title>Dashboard - Soleda</title>
</svelte:head>

<div class="bg-gradient-to-br from-slate-50 to-slate-100 min-h-screen p-4 md:p-6">
  <div class="container mx-auto">
    <div class="mb-4">
      <div class="w-full flex justify-between items-center px-2 py-1">
        <!-- Left side: logo or brand -->
        <div class="w-1/6 flex items-center">
        </div>
        
        <!-- Center: Dashboard title -->
        <div class="w-4/6 flex justify-center">
          {#if editingTitle}
            <input type="text" bind:this={titleInputRef} bind:value={dashboardTitle} on:blur={saveTitle} on:keydown={handleTitleKeydown}
              class="font-bold text-center bg-transparent m-0 border-0 px-2 py-0 duration-200 min-w-md w-full text-3xl"
            />
          {:else}
            <h1 class="font-bold text-center text-slate-800 hover:text-blue-700 hover:cursor-text 
              open-sans-font relative group min-w-md w-full m-0 text-3xl"
              on:click={startEditingTitle} title="Click to edit dashboard title">
              {dashboardTitle}
            </h1>
          {/if}
        </div>
        
        <!-- Right side: action buttons -->
        <div class="w-1/6 flex justify-end gap-2">
          <button 
            class="p-2 bg-white rounded-full shadow-sm hover:shadow-md hover:bg-slate-50 text-slate-700 hover:text-blue-600 transition-all duration-200"
            on:click={undo} title="Undo last action">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4 md:w-5 md:h-5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 15L3 9m0 0l6-6M3 9h12a6 6 0 010 12h-3" />
            </svg>
          </button>
          
          <button class="p-2 bg-white rounded-full shadow-sm hover:shadow-md hover:bg-slate-50 text-slate-700 hover:text-blue-600 transition-all duration-200"
            on:click={redo} title="Redo last action">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4 md:w-5 md:h-5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M15 15l6-6m0 0l-6-6m6 6H9a6 6 0 000 12h3" />
            </svg>
          </button>
          
          <button 
            class="p-2 bg-white rounded-full shadow-sm hover:shadow-md hover:bg-slate-50 text-slate-700 hover:text-blue-600 transition-all duration-200"
            on:click={clearDashboard}
            title="Clear dashboard"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4 md:w-5 md:h-5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
            </svg>
          </button>
        </div>
      </div>
    </div>
    
    <!-- Dashboard Grid -->
    <div class="bg-white p-4 rounded-xl shadow-sm hover:shadow-md transition-shadow duration-300">
      {#if browser}
        <div 
          class="dashboard-grid" 
          style="grid-template-columns: repeat({cols}, 1fr); grid-template-rows: repeat({rows}, 125px);"
        >
          <!-- Render grid cells -->
          {#each gridCells as cell (cell.row + '-' + cell.col)}
            {#if isEmptyCell(cell.row, cell.col)}
              <div 
                class="empty-cell"
                class:drag-over={isDragOverCell(cell.row, cell.col)}
                class:invalid={isDragOverCell(cell.row, cell.col) && isInvalidPlacement}
                style="grid-area: {cell.row + 1} / {cell.col + 1} / span 1 / span 1;"
                on:click={(e) => openElementMenu(cell.row, cell.col, e)}
                on:dragover={(e) => handleDragOver(e, cell.row, cell.col)}
                on:drop={(e) => handleDrop(e, cell.row, cell.col)}
              >
                <div class="add-icon-container opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5 md:w-6 md:h-6">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                  </svg>
                </div>
              </div>
            {/if}
          {/each}
          
          <!-- Render dashboard elements -->
          {#each $dashboardElements as element (element.id)}
            <div 
              class="dashboard-element"
              class:dragging={isDragging && draggedElementId === element.id}
              style="
                grid-area: {element.location.row + 1} / {element.location.col + 1} / 
                span {element.size.rows} / span {element.size.cols};
              "
              draggable="true"
              on:dragstart={(e) => handleDragStart(e, element)}
              on:dragend={handleDragEnd}
            >
              <ElementFactory 
                {element} 
                on:resize={(e) => resizeElement(element.id, e.detail)}
                on:remove={() => removeElement(element.id)}
                on:update={(e) => update_handler(element.id, e.detail)}
              />
              
              <!-- Resize handles -->
              <div class="resize-handle resize-handle-se" on:mousedown={(e) => handleResizeStart(e, element, 'se')}></div>
              <div class="resize-handle resize-handle-e" on:mousedown={(e) => handleResizeStart(e, element, 'e')}></div>
              <div class="resize-handle resize-handle-s" on:mousedown={(e) => handleResizeStart(e, element, 's')}></div>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  </div>
</div>

<!-- Element Selection Menu -->
{#if showElementMenu}
  <ElementSelectionMenu 
    position={menuPosition} 
    on:close={closeElementMenu}
    on:select={handleElementSelect}
  />
{/if}

<style>
  .dashboard-grid {
    display: grid;
    gap: 12px;
    position: relative;
    min-height: 600px;
  }
  
  .empty-cell {
    background-color: #f8fafc;
    border: 1px dashed #e2e8f0;
    border-radius: 0.5rem;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s ease;
    z-index: 1;
  }
  
  .empty-cell:hover {
    background-color: #f1f5f9;
    border-color: #cbd5e1;
  }
  
  .empty-cell.drag-over {
    background-color: rgba(59, 130, 246, 0.08);
    border-color: #60a5fa;
    z-index: 3;
  }
  
  .empty-cell.drag-over.invalid {
    background-color: rgba(239, 68, 68, 0.08);
    border-color: #ef4444;
  }
  
  .add-icon-container {
    color: #64748b;
  }
  
  .dashboard-element {
    background-color: white;
    border-radius: 0.5rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.04);
    overflow: hidden;
    transition: all 0.2s ease;
    position: relative;
    z-index: 2;
  }
  
  .dashboard-element:hover {
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05), 0 2px 4px rgba(0, 0, 0, 0.05);
  }
  
  .dashboard-element.dragging {
    visibility: hidden;  /* Hide the original element */
  }
  
  .resize-handle {
    position: absolute;
    background-color: rgba(59, 130, 246, 0.5);
    z-index: 5;
    opacity: 0;
    transition: opacity 0.2s ease;
  }
  
  .dashboard-element:hover .resize-handle {
    opacity: 0.8;
  }
  
  .resize-handle:hover {
    background-color: rgba(37, 99, 235, 0.8);
  }
  
  .resize-handle-se {
    width: 10px;
    height: 10px;
    right: 2px;
    bottom: 2px;
    cursor: nwse-resize;
    border-radius: 50%;
  }
  
  .resize-handle-e {
    width: 4px;
    height: calc(100% - 14px);
    right: 2px;
    top: 2px;
    cursor: ew-resize;
    border-radius: 2px;
  }
  
  .resize-handle-s {
    width: calc(100% - 14px);
    height: 4px;
    bottom: 2px;
    left: 2px;
    cursor: ns-resize;
    border-radius: 2px;
  }
</style>