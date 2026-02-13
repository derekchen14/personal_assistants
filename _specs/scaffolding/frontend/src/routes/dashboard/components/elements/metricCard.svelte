<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  
  // Props
  export let content = {
    title: 'Metric',
    value: '0',
    changePercent: 0
  };
  
  // State
  let isEditing = false;
  let editedContent = { ...content };
  
  // Event dispatcher
  const dispatch = createEventDispatcher();
  
  // Format value for display
  function formatValue(val) {
    // Check if the value is a purely numeric string
    if (typeof val === 'string' && !isNaN(parseFloat(val)) && /^-?\d+(\.\d+)?$/.test(val)) {
      return parseFloat(val).toLocaleString();
    }
    // Return the value as-is if it contains non-numeric characters like "2K"
    return val;
  }
  
  // Format percentage for display
  function formatPercentage(percent) {
    if (typeof percent === 'number') {
      return percent.toFixed(1) + '%';
    }
    return percent;
  }
  
  // Start editing
  function startEditing() {
    editedContent = { ...content };
    isEditing = true;
  }
  
  // Save changes
  function saveChanges() {
    const numericPercent = parseFloat(editedContent.changePercent);
    
    const updatedContent = {
      title: editedContent.title,
      value: editedContent.value,
      changePercent: isNaN(numericPercent) ? 0 : numericPercent
    };
    
    isEditing = false;
    dispatch('update', updatedContent);
  }
  
  // Handle keydown in the edit form
  function handleKeydown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      
      // Get all input elements in the form
      const inputs = Array.from(document.querySelectorAll('.edit-form input'));
      const currentIndex = inputs.indexOf(event.target);
      
      if (currentIndex < inputs.length - 1) {
        // Move focus to the next input
        inputs[currentIndex + 1].focus();
      } else {
        // If it's the last input, save and unfocus
        saveChanges();
      }
    } else if (event.key === 'Escape') {
      isEditing = false;
    }
  }
  
  // Handle blur event
  function handleBlur(event) {
    // Only save on blur if it's not triggered by moving between inputs
    setTimeout(() => {
      // Check if the new active element is another input in our form
      const activeElement = document.activeElement;
      const inputs = Array.from(document.querySelectorAll('.edit-form input'));
      
      if (!inputs.includes(activeElement)) {
        saveChanges();
      }
    }, 0);
  }
</script>

<div class="metric-card">
  {#if isEditing}
    <div class="edit-form">
      <div class="form-group">
        <label for="metric-title">Title</label>
        <input 
          type="text" 
          id="metric-title" 
          bind:value={editedContent.title} 
          placeholder="Metric Title"
          on:keydown={handleKeydown}
          on:blur={handleBlur}
        />
      </div>
      
      <div class="form-group">
        <label for="metric-value">Value</label>
        <input 
          type="text" 
          id="metric-value" 
          bind:value={editedContent.value} 
          placeholder="Value"
          on:keydown={handleKeydown}
          on:blur={handleBlur}
        />
      </div>
      
      <div class="form-group">
        <label for="metric-change">Change % (+ or -)</label>
        <input 
          type="number" 
          id="metric-change" 
          bind:value={editedContent.changePercent} 
          placeholder="Change percentage"
          step="0.1"
          on:keydown={handleKeydown}
          on:blur={handleBlur}
        />
      </div>
    </div>
  {:else}
    <div class="metric-display" on:click={startEditing}>
      <div class="metric-title">{content.title}</div>
      <div class="metric-value">{formatValue(content.value)}</div>
      
      {#if content.changePercent !== 0}
        <div 
          class="metric-change" 
          class:positive={content.changePercent > 0 && !content.title.includes('CPC')}
          class:negative={content.changePercent < 0 && !content.title.includes('CPC')}
          class:cpc-positive={content.changePercent > 0 && content.title.includes('CPC')}
          class:cpc-negative={content.changePercent < 0 && content.title.includes('CPC')}
        >
          {content.changePercent > 0 ? '↑' : '↓'} {formatPercentage(Math.abs(content.changePercent))}
        </div>
      {:else}
        <div class="metric-change neutral">0%</div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .metric-card {
    width: 100%;
    height: 100%;
    display: flex;
    justify-content: center;
    align-items: center;
    background-color: white;
    border-radius: 0.375rem;
  }
  
  .metric-display {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    padding: 0.75rem;
    cursor: pointer;
  }
  
  .metric-title {
    font-size: 0.875rem;
    color: #6b7280;
    margin-bottom: 0.25rem;
    text-align: center;
  }
  
  .metric-value {
    font-size: 1.5rem;
    font-weight: 600;
    color: #111827;
    margin-bottom: 0.25rem;
    text-align: center;
  }
  
  .metric-change {
    font-size: 0.875rem;
    font-weight: 500;
    padding: 0.125rem 0.5rem;
    border-radius: 9999px;
    text-align: center;
  }
  
  .metric-change.positive {
    color: #10b981;
    background-color: rgba(16, 185, 129, 0.1);
  }
  
  .metric-change.negative {
    color: #ef4444;
    background-color: rgba(239, 68, 68, 0.1);
  }
  
  .metric-change.cpc-positive {
    color: #ef4444;
    background-color: rgba(239, 68, 68, 0.1);
  }
  
  .metric-change.cpc-negative {
    color: #10b981;
    background-color: rgba(16, 185, 129, 0.1);
  }
  
  .metric-change.neutral {
    color: #6b7280;
    background-color: rgba(107, 114, 128, 0.1);
  }
  
  .edit-form {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    padding: 0.75rem;
    gap: 0.5rem;
    overflow-y: auto;
  }
  
  .form-group {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }
  
  label {
    font-size: 0.75rem;
    color: #4b5563;
  }
  
  input {
    padding: 0.375rem 0.5rem;
    border: 1px solid #d1d5db;
    border-radius: 0.25rem;
    font-size: 0.875rem;
  }
</style>