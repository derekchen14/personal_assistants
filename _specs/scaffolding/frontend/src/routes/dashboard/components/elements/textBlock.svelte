<script lang="ts">
  import { createEventDispatcher } from 'svelte';  

  export let content = {
    text: 'New text block',
    format: {
      bold: false,
      italic: false,
      underline: false
    }
  };
  
  // State
  let isEditing = false;
  let textContent = content.text;
  
  // Event dispatcher
  const dispatch = createEventDispatcher();
  
  // Add a ref for the container
  let editingContainerRef;
  
  // Begin editing
  function startEditing() {
    isEditing = true;
  }
  
  // Save changes
  function saveChanges() {
    isEditing = false;
    const updatedContent = {
      ...content,
      text: textContent
    };
    // Directly update the element content in the store
    dispatch('update', updatedContent);
  }
  
  // Handle editor blur event to save content
  function handleBlur(event) {
    // Check if we're clicking inside the editing container
    if (editingContainerRef && editingContainerRef.contains(event.relatedTarget)) {
      // Clicked inside the container, don't save or exit editing mode
      return;
    }
    
    // Otherwise, save changes as we're clicking outside
    saveChanges();
  }
  
  // Toggle text formatting without exiting edit mode
  function toggleFormat(format) {
    const updatedFormat = {
      ...content.format,
      [format]: !content.format[format]
    };
    
    // Update the content object directly
    content = {
      ...content,
      format: {...updatedFormat}
    };
    
    // Dispatch the update event but don't save/exit editing mode
    dispatch('update', content);
  }
  
  // Handle keydown events
  function handleKeydown(event) {
    // Save on Ctrl+Enter or Cmd+Enter
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
      saveChanges();
    }
    
    // Cancel on Escape
    if (event.key === 'Escape') {
      textContent = content.text;
      isEditing = false;
    }
  }
</script>

<div class="text-block-container">
  {#if isEditing}
    <div class="editing-container" bind:this={editingContainerRef}>
      <div class="format-toolbar">
        <div 
          class="format-btn-container" 
          on:mousedown|preventDefault={() => {
            console.log('Bold clicked');
            toggleFormat('bold');
          }}
        >
          <button 
            class="format-btn" 
            class:active={content.format.bold}
            type="button"
            title="Bold"
          >
            <div class="icon-wrapper">
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M6 4h8a4 4 0 0 1 4 4 4 4 0 0 1-4 4H6z"/>
                <path d="M6 12h9a4 4 0 0 1 4 4 4 4 0 0 1-4 4H6z"/>
              </svg>
            </div>
          </button>
        </div>
        
        <div 
          class="format-btn-container" 
          on:mousedown|preventDefault={() => toggleFormat('italic')}
        >
          <button 
            class="format-btn" 
            class:active={content.format.italic}
            type="button"
            title="Italic"
          >
            <div class="icon-wrapper">
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="19" y1="4" x2="10" y2="4"/>
                <line x1="14" y1="20" x2="5" y2="20"/>
                <line x1="15" y1="4" x2="9" y2="20"/>
              </svg>
            </div>
          </button>
        </div>
        
        <div 
          class="format-btn-container" 
          on:mousedown|preventDefault={() => toggleFormat('underline')}
        >
          <button 
            class="format-btn" 
            class:active={content.format.underline}
            type="button"
            title="Underline"
          >
            <div class="icon-wrapper">
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M6 3v7a6 6 0 0 0 6 6 6 6 0 0 0 6-6V3"/>
                <line x1="4" y1="21" x2="20" y2="21"/>
              </svg>
            </div>
          </button>
        </div>
      </div>
      
      <textarea 
        bind:value={textContent}
        on:keydown={handleKeydown}
        on:blur={handleBlur}
        class="text-editor"
        class:bold={content.format.bold}
        class:italic={content.format.italic}
        class:underline={content.format.underline}
        rows="5"
        placeholder="Enter text here..."
        autofocus
      ></textarea>
    </div>
  {:else}
    <div 
      class="text-content"
      on:click={startEditing}
      class:bold={content.format.bold}
      class:italic={content.format.italic}
      class:underline={content.format.underline}
    >
      {content.text || 'Click to edit text...'}
    </div>
  {/if}
</div>

<style>
  .text-block-container {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
  }
  
  .text-content {
    font-size: 1.25rem;
    flex: 1;
    padding: 8px;
    color: #374151;
    cursor: text;
    white-space: pre-wrap;
    overflow: auto;
  }
  
  .text-content.bold {
    font-weight: bold;
  }
  
  .text-content.italic {
    font-style: italic;
  }
  
  .text-content.underline {
    text-decoration: underline;
  }
  
  .editing-container {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
  }
  
  .format-toolbar {
    display: flex;
    padding: 4px;
    border-bottom: 1px solid #e5e7eb;
    gap: 4px;
    justify-content: flex-end;
  }
  
  .format-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    background: none;
    border: 1px solid transparent;
    border-radius: 4px;
    color: #6b7280;
    cursor: pointer;
    padding: 0;
  }
  
  .format-btn:hover {
    background-color: #f3f4f6;
  }
  
  .format-btn.active {
    background-color: #e5e7eb;
    color: #374151;
    border-color: #d1d5db;
  }
  
  .text-editor {
    flex: 1;
    padding: 8px;
    border: none;
    resize: none;
    font-family: inherit;
    font-size: 1.25rem;
    outline: none;
  }
  
  .text-editor.bold {
    font-weight: bold;
  }
  
  .text-editor.italic {
    font-style: italic;
  }
  
  .text-editor.underline {
    text-decoration: underline;
  }
  
  .icon-wrapper {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 100%;
    pointer-events: none;
  }
  
  .format-btn-container {
    cursor: pointer;
  }
</style>