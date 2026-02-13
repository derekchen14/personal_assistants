<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { ELEMENT_TYPES, updateElementContent } from '../stores/dashboard';
  import TextBlock from './elements/textBlock.svelte';
  import MetricCard from './elements/metricCard.svelte';
  import PlotlyChart from './elements/plotlyChart.svelte';
  import UploadedFile from './elements/uploadedFile.svelte';
  
  // Props
  export let element;
  
  // Event dispatcher
  const dispatch = createEventDispatcher();
  
  // Resize the element
  function handleResize(newSize) {
    dispatch('resize', newSize);
  }
  
  // Remove the element
  function handleRemove() {
    dispatch('remove');
  }
  
  // Update element content
  function handleUpdate(id, updatedContent) {
    updateElementContent(id, updatedContent);
  }
</script>

<div class="element-container">
  <div class="element-controls">
    <div class="control-actions">
      <button 
        class="control-btn drag-handle" 
        title="Drag to move"
      >
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 3.75v4.5m0-4.5h4.5m-4.5 0L9 9M3.75 20.25v-4.5m0 4.5h4.5m-4.5 0L9 15M20.25 3.75h-4.5m4.5 0v4.5m0-4.5L15 9m5.25 11.25h-4.5m4.5 0v-4.5m0 4.5L15 15" />
        </svg>
      </button>
      
      <button 
        class="control-btn remove" 
        on:click={handleRemove}
        title="Remove element"
      >
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  </div>
  
  <div class="element-content">
    <!-- Render appropriate component based on element type -->
    {#if element.type === ELEMENT_TYPES.TEXT_BLOCK}
      <TextBlock 
        content={element.content} 
        on:update={(e) => handleUpdate(element.id, e.detail)}
      />
    {:else if element.type === ELEMENT_TYPES.METRIC_CARD}
      <MetricCard 
        content={element.content} 
        on:update={(e) => handleUpdate(element.id, e.detail)}
      />
    {:else if element.type === ELEMENT_TYPES.PLOTLY_CHART}
      <PlotlyChart 
        content={element.content} 
        on:update={(e) => handleUpdate(element.id, e.detail)}
      />
    {:else if element.type === ELEMENT_TYPES.UPLOADED_FILE}
      <UploadedFile 
        content={element.content} 
        on:update={(e) => handleUpdate(element.id, e.detail)}
      />
    {/if}
  </div>
</div>

<style>
  .element-container {
    width: 100%;
    height: 100%;
    position: relative;
    display: flex;
    flex-direction: column;
  }
  
  .element-controls {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    display: flex;
    justify-content: flex-start;
    padding: 4px;
    z-index: 10;
    opacity: 0;
    transition: opacity 0.2s ease;
    background: linear-gradient(to bottom, rgba(255, 255, 255, 0.9), rgba(255, 255, 255, 0));
    pointer-events: none;
  }
  
  .element-container:hover .element-controls {
    opacity: 1;
  }
  
  .control-actions {
    display: flex;
    gap: 4px;
    pointer-events: auto;
  }
  
  .control-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border: none;
    background-color: white;
    border-radius: 50%;
    cursor: pointer;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
    pointer-events: auto;
  }
  
  .control-btn.drag-handle {
    color: #3b82f6;
    cursor: move;
  }
  
  .control-btn.remove {
    color: #ef4444;
  }
  
  .element-content {
    flex: 1;
    width: 100%;
    height: 100%;
    padding: 8px;
    overflow: auto;
    display: flex;
  }
</style>