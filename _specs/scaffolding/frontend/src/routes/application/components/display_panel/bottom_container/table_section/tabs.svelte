<script>
  import { selectTab, selectedTable, selectedSpreadsheet, sheetData } from '@store';
  
  // Track state for context menu
  let showContextMenu = false;
  let contextMenuX = 0;
  let contextMenuY = 0;
  let isDeleting = false;
  
  // For notifications
  let showNotification = false;
  let notificationMessage = '';
  let notificationColor = '';
  let notificationTimeout;

  function showToast(message, type = 'success') {
    // Clear any existing timeout
    if (notificationTimeout) {
      clearTimeout(notificationTimeout);
    }
    
    // Set notification content
    notificationMessage = message;
    notificationColor = type === 'success' ? 'bg-green-600' : 'bg-red-600';
    showNotification = true;
    
    // Auto-hide after 4 seconds
    notificationTimeout = setTimeout(() => {
      showNotification = false;
    }, 2000);
  }

  // Handle right-click on tab
  function handleRightClick(event, tab) {
    event.preventDefault();
    selectTab(tab); // Select the tab on right-click
    
    // Get the button element that was right-clicked
    const button = event.currentTarget;
    const rect = button.getBoundingClientRect();
    
    // Standard menu height (if we don't have it yet)
    const estimatedMenuHeight = 40; // Height of a menu with 2 items
    const menuWidth = 150; // Estimated menu width
    
    // Position the menu above the tab and centered horizontally
    contextMenuX = rect.left + (rect.width / 2) - (menuWidth / 2); // Center over the tab
    contextMenuY = rect.top - estimatedMenuHeight; // Position above the tab
    
    showContextMenu = true;
    
    // After menu is shown, adjust position if needed
    setTimeout(() => {
      const menu = document.querySelector('.context-menu');
      if (menu) {
        const menuRect = menu.getBoundingClientRect();
        
        // If menu would go off left or right edge of screen, adjust accordingly
        if (contextMenuX < 5) {
          contextMenuX = 5; // 5px from left edge of screen
        } else if (contextMenuX + menuRect.width > window.innerWidth - 5) {
          contextMenuX = window.innerWidth - menuRect.width - 5; // 5px from right edge of screen
        }
      }
    }, 0);
  }

  function handleEdit() {
    console.log('Edit tab:', selectedTable);
    showContextMenu = false;
  }

  async function deleteTable(tableName) {
    try {
      isDeleting = true;
      const response = await fetch(`/api/table/${tableName}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.message || 'Failed to delete table, table state can be corrupted.');
      }
      
      return true;
    } catch (error) {
      console.error('Error deleting table:', error);
      showToast(`Error: ${error.message}`, 'error');
      return false;
    } finally {
      isDeleting = false;
    }
  }

  async function handleDelete() {
    showContextMenu = false;
    
    // Confirm deletion with the user
    if (!confirm(`Are you sure you want to delete the table "${$selectedTable}"? This action cannot be undone.`)) {
      return;
    }
    
    const success = await deleteTable($selectedTable);
    
    if (success) {
      showToast(`Table "${$selectedTable}" deleted successfully`);
      sheetData.update(currentSheet => {
        delete currentSheet[$selectedTable];
        return currentSheet;
      });
      
      // Update the UI by removing the deleted table from the spreadsheet tabs
      if ($selectedSpreadsheet) {
        // Create a new array without the deleted table
        const updatedTabs = $selectedSpreadsheet.tabNames.filter(tab => tab !== $selectedTable);
        
        // Update the store
        selectedSpreadsheet.update(spreadsheet => ({
          ...spreadsheet,
          tabNames: updatedTabs
        }));
        
        // If there are no more tables, redirect to application page
        if (updatedTabs.length === 0) {
          window.location.href = '/application';
          return;
        }
        
        // If the deleted table was selected, select the first available tab
        if ($selectedTable === $selectedTable) {
          selectTab(updatedTabs[0]);
        }
      }
    }
  }
  function handleClickOutside(event) {
    if (showContextMenu) {
      showContextMenu = false;
    }
  }
</script>

<svelte:window on:click={handleClickOutside} />

<nav class="tabs absolute z-10 whitespace-nowrap mt-0 pl-6 bottom-4 hidden
  col-start-5 col-span-8 md:block lg:col-start-6 lg:col-span-7">
  {#if $selectedSpreadsheet && $selectedSpreadsheet.tabNames}
    {#each $selectedSpreadsheet.tabNames as tab}
      <button class="inline relative tab-button cursor-pointer 
        text-sm font-medium text-gray-500 hover:text-teal-400"
        class:selected={$selectedTable === tab} 
        on:click={() => selectTab(tab)}
        on:contextmenu={(e) => handleRightClick(e, tab)}>
        {tab}
      </button>
    {/each}
  {/if}
</nav>

{#if showContextMenu}
  <div 
    class="context-menu"
    style="position: fixed; left: {contextMenuX}px; top: {contextMenuY}px;"
  >
    <ul>
      <!-- <li class="edit-option" on:click={handleEdit}>Edit</li> -->
      <li class="delete-option" class:disabled={isDeleting} on:click={handleDelete}>
        {#if isDeleting}
          Deleting...
        {:else}
          Delete
        {/if}
      </li>
    </ul>
  </div>
{/if}

{#if showNotification}
  <div class="fixed bottom-4 left-1/2 transform -translate-x-1/2 {notificationColor} text-white px-4 py-2 rounded-md shadow-md z-50 transition-opacity duration-300">
    {notificationMessage}
  </div>
{/if}

<style>
  .tab-button {
    padding: 0.9em 1.6em 0.2em 1.6em;
    margin: 0 -4px;
  }
  .tab-button::before {
    content: '';
    min-height: 3em;
    background-color: #e2e8f0;  /* slate-200 */
    border-color: #d1d5db; /* gray-300 */
    position: absolute;
    top: 0.5em; right: 0; bottom: 0; left: 0;
    z-index: -1;
    border-top: none;
    border-width: 2px;
    border-radius: 0 0 10px 10px;
    transform: perspective(5px) rotateX(-2deg);
    transform-origin: top;
  }
  .tab-button:hover::before {
    background-color: #f1f5f9;  /* slate-100 */
    border-color: #94a3b8;  /* slate-400 */
  }
  .tab-button.selected {
    z-index: 2;
  }
  .tab-button.selected::before {
    background-color: #f8fafc;  /* slate-50 */
    border-color: #94a3b8;  /* slate-400 */
    box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
    border-width: 1px;
    border-bottom-width: 2px;
  }
  .tab-button.selected:hover::before {
    color: #14b8a6;  /* teal-400 */
    background-color: #f1f5f9;  /* slate-100 */
  }

  /* Context menu styles */
  .context-menu {
    background-color: white;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
    z-index: 100;
    min-width: 150px;
    padding: 6px 0;
  }
  
  .context-menu ul {
    list-style: none;
    padding: 0;
    margin: 0;
  }
  
  .context-menu li {
    padding: 6px 24px;
    cursor: pointer;
    font-size: 14px;
    color: #202124;
    transition: background-color 0.15s ease, color 0.15s ease;
  }
  
  .context-menu li:first-child:hover {
    background-color: #f1f5f9;
    color: #14b8a6;  /* teal-400 - matches tab hover color */
  }
  
  .context-menu li:last-child:hover {
    background-color: #fee2e2;  /* light red background */
    color: #ef4444;  /* red-500 */
  }

  .context-menu li.disabled {
    cursor: not-allowed;
    opacity: 0.6;
    color: #6b7280;
  }

  .context-menu li.disabled:hover {
    background-color: inherit;
    color: #6b7280;
  }
</style>