<script lang="ts">
  import { createEventDispatcher, onMount, onDestroy, afterUpdate } from 'svelte';
  
  // Props
  export let content = {
    data: [],
    layout: {
      title: 'Chart Title',
      showlegend: true,
      autosize: true,
      margin: { l: 50, r: 50, b: 50, t: 50, pad: 4 }
    }
  };
  
  // State variables
  let chartContainer;
  let Plotly;
  let isEditing = false;
  let editedLayout = {};
  
  // Event dispatcher
  const dispatch = createEventDispatcher();
  
  // Default demo data for new charts
  const defaultData = [
    {
      x: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
      y: [20, 14, 25, 16, 18, 22],
      type: 'bar'
    }
  ];
  
  // Get current data
  $: chartData = content.data && content.data.length > 0 ? content.data : defaultData;
  
  // Load Plotly dynamically
  async function loadPlotly() {
    if (!Plotly) {
      try {
        const module = await import('plotly.js-dist');
        Plotly = module.default;
        return true;
      } catch (error) {
        console.error('Failed to load Plotly:', error);
        return false;
      }
    }
    return true;
  }
  
  // Render or update the chart
  async function renderChart() {
    if (!chartContainer) return;
    
    const plotlyLoaded = await loadPlotly();
    if (!plotlyLoaded) return;
    
    try {
      // If chart already exists, update it
      if (chartContainer._Plotly) {
        Plotly.react(chartContainer, chartData, content.layout, { responsive: true });
      } else {
        // Otherwise create it
        Plotly.newPlot(chartContainer, chartData, content.layout, { responsive: true });
      }
    } catch (error) {
      console.error('Error rendering Plotly chart:', error);
    }
  }
  
  // Start editing chart properties
  function startEditing() {
    editedLayout = JSON.parse(JSON.stringify(content.layout || {}));
    isEditing = true;
  }
  
  // Save changes
  function saveChanges() {
    // Try to parse layout as JSON
    try {
      const updatedContent = {
        ...content,
        layout: editedLayout
      };
      
      isEditing = false;
      dispatch('update', updatedContent);
      
      // Re-render chart with updated layout
      setTimeout(renderChart, 0);
    } catch (error) {
      console.error('Invalid layout JSON:', error);
      // You could add error handling/messaging here
    }
  }
  
  // Cancel editing
  function cancelEditing() {
    isEditing = false;
  }
  
  // Clean up on component destroy
  onDestroy(() => {
    if (chartContainer && Plotly) {
      Plotly.purge(chartContainer);
    }
  });
  
  // Render chart on mount and updates
  onMount(renderChart);
  afterUpdate(renderChart);
</script>

<div class="plotly-chart-container">
  {#if isEditing}
    <div class="edit-form">
      <div class="form-group">
        <label for="chart-title">Chart Title</label>
        <input 
          type="text" 
          id="chart-title" 
          bind:value={editedLayout.title} 
          placeholder="Chart Title"
        />
      </div>
      
      <div class="form-group">
        <label>
          <input 
            type="checkbox" 
            bind:checked={editedLayout.showlegend} 
          />
          Show Legend
        </label>
      </div>
      
      <div class="form-group">
        <label>
          <input 
            type="checkbox" 
            bind:checked={editedLayout.autosize} 
          />
          Auto Size
        </label>
      </div>
      
      <div class="form-group">
        <label for="margin-top">Top Margin</label>
        <input 
          type="number" 
          id="margin-top" 
          bind:value={editedLayout.margin.t} 
          min="0"
          max="100"
        />
      </div>
      
      <div class="form-group">
        <label for="margin-right">Right Margin</label>
        <input 
          type="number" 
          id="margin-right" 
          bind:value={editedLayout.margin.r} 
          min="0"
          max="100"
        />
      </div>
      
      <div class="form-group">
        <label for="margin-bottom">Bottom Margin</label>
        <input 
          type="number" 
          id="margin-bottom" 
          bind:value={editedLayout.margin.b} 
          min="0"
          max="100"
        />
      </div>
      
      <div class="form-group">
        <label for="margin-left">Left Margin</label>
        <input 
          type="number" 
          id="margin-left" 
          bind:value={editedLayout.margin.l} 
          min="0"
          max="100"
        />
      </div>
      
      <div class="edit-actions">
        <button class="cancel-btn" on:click={cancelEditing}>Cancel</button>
        <button class="save-btn" on:click={saveChanges}>Save</button>
      </div>
    </div>
  {:else}
    <div class="chart-container-wrapper">
      <div class="chart-options">
        <button class="edit-btn" on:click={startEditing}>
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4">
            <path stroke-linecap="round" stroke-linejoin="round" d="M10.5 6h9.75M10.5 6a1.5 1.5 0 11-3 0m3 0a1.5 1.5 0 10-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-9.75 0h9.75" />
          </svg>
          <span>Edit</span>
        </button>
      </div>
      <div bind:this={chartContainer} class="chart-container"></div>
    </div>
  {/if}
</div>

<style>
  .plotly-chart-container {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
  }
  
  .chart-container-wrapper {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    position: relative;
  }
  
  .chart-options {
    position: absolute;
    top: 8px;
    right: 8px;
    z-index: 5;
    display: flex;
    opacity: 0;
    transition: opacity 0.2s ease;
  }
  
  .chart-container-wrapper:hover .chart-options {
    opacity: 1;
  }
  
  .edit-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 4px 8px;
    background-color: white;
    border: 1px solid #e5e7eb;
    border-radius: 4px;
    font-size: 0.75rem;
    color: #4b5563;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
    cursor: pointer;
  }
  
  .edit-btn:hover {
    background-color: #f9fafb;
  }
  
  .chart-container {
    width: 100%;
    height: 100%;
  }
  
  .edit-form {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    padding: 12px;
    overflow-y: auto;
    gap: 8px;
  }
  
  .form-group {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  
  .form-group label {
    font-size: 0.75rem;
    color: #4b5563;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  
  .form-group input[type="text"],
  .form-group input[type="number"] {
    padding: 4px 8px;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    font-size: 0.875rem;
  }
  
  .form-group input[type="checkbox"] {
    margin: 0;
  }
  
  .edit-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: auto;
    padding-top: 12px;
  }
  
  .cancel-btn {
    padding: 4px 8px;
    background: none;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    font-size: 0.75rem;
    color: #4b5563;
    cursor: pointer;
  }
  
  .save-btn {
    padding: 4px 8px;
    background-color: #3b82f6;
    border: 1px solid #2563eb;
    border-radius: 4px;
    font-size: 0.75rem;
    color: white;
    cursor: pointer;
  }
</style>