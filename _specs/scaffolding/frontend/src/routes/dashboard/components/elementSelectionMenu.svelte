<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import { ELEMENT_TYPES } from '../stores/dashboard';
  
  // Props
  export let position = { x: 0, y: 0 };
  
  // Element menu options
  const menuOptions = [
    {
      type: ELEMENT_TYPES.TEXT_BLOCK,
      label: 'Text Block',
      icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25H12" />
            </svg>`
    },
    {
      type: ELEMENT_TYPES.METRIC_CARD,
      label: 'Metric Card',
      icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
            </svg>`
    },
    // For now, we only support importing plotly charts from the application
    // {
    //   type: ELEMENT_TYPES.PLOTLY_CHART,
    //   label: 'Chart',
    //   icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5">
    //           <path stroke-linecap="round" stroke-linejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
    //         </svg>`
    // },
    {
      type: ELEMENT_TYPES.UPLOADED_FILE,
      label: 'Upload File',
      icon: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
            </svg>`
    }
  ];
  
  // State variables
  let menuElement;
  
  // Event dispatcher
  const dispatch = createEventDispatcher();
  
  // Handle element selection
  function selectElement(type) {
    dispatch('select', { type });
  }
  
  // Close the menu
  function closeMenu() {
    dispatch('close');
  }
  
  // Handle click outside menu
  function handleClickOutside(event) {
    if (menuElement && !menuElement.contains(event.target)) {
      closeMenu();
    }
  }
  
  // Adjust position to ensure menu stays within viewport
  function adjustPosition() {
    if (!menuElement) return { x: position.x, y: position.y };
    
    const menuRect = menuElement.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    
    let x = position.x;
    let y = position.y;
    
    // Adjust horizontally if needed
    if (x + menuRect.width > viewportWidth) {
      x = viewportWidth - menuRect.width - 10;
    }
    
    // Adjust vertically if needed
    if (y + menuRect.height > viewportHeight) {
      y = viewportHeight - menuRect.height - 10;
    }
    
    return { x, y };
  }
  
  onMount(() => {
    // Add global click handler
    document.addEventListener('mousedown', handleClickOutside);
    
    // Clean up on destroy
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  });
  
  // Calculate adjusted position
  $: adjustedPosition = adjustPosition();
</script>

<div 
  bind:this={menuElement}
  class="element-menu"
  style="left: {adjustedPosition.x}px; top: {adjustedPosition.y}px;"
>
  <div class="menu-header">
    <h3>Add Element</h3>
    <button class="close-btn" on:click={closeMenu}>
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
      </svg>
    </button>
  </div>
  
  <div class="menu-options">
    {#each menuOptions as option}
      <button 
        class="menu-option" 
        on:click={() => selectElement(option.type)}
      >
        <div class="option-icon" aria-hidden="true">
          {@html option.icon}
        </div>
        <span class="option-label">{option.label}</span>
      </button>
    {/each}
  </div>
</div>

<style>
  .element-menu {
    position: fixed;
    z-index: 100;
    width: 200px;
    background-color: white;
    border-radius: 0.375rem;
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
    overflow: hidden;
  }
  
  .menu-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.75rem 1rem;
    border-bottom: 1px solid #e5e7eb;
  }
  
  .menu-header h3 {
    font-size: 0.875rem;
    font-weight: 600;
    margin: 0;
    color: #374151;
  }
  
  .close-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    color: #6b7280;
    background: none;
    border: none;
    cursor: pointer;
  }
  
  .menu-options {
    padding: 0.5rem;
  }
  
  .menu-option {
    display: flex;
    align-items: center;
    width: 100%;
    padding: 0.5rem;
    border-radius: 0.25rem;
    background: none;
    border: none;
    cursor: pointer;
    transition: all 0.2s ease;
    text-align: left;
  }
  
  .menu-option:hover {
    background-color: #f3f4f6;
  }
  
  .option-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    color: #4b5563;
    margin-right: 0.75rem;
  }
  
  .option-label {
    font-size: 0.875rem;
    color: #374151;
  }
</style>