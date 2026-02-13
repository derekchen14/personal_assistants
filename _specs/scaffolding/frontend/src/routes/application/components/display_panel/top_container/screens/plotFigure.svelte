<script lang="ts">
  import { userActions, interactionView } from '@store';
  import { tick } from 'svelte';
  import { goto } from '$app/navigation';
  import { addElement, ELEMENT_TYPES } from '../../../../../dashboard/stores/dashboard';

  window.PlotlyConfig = { MathJaxConfig: 'local' };
  window.PLOTLYENV = window.PLOTLYENV || {};

  let Plotly;
  let currentFigPayload;
  let isHovered = false;
  let showNotification = false;

  import('plotly.js-dist').then((module) => {
    Plotly = module.default;
  });

  const addToDashboard = () => {
    if (currentFigPayload) {
      // Instead of using localStorage, directly use the dashboard store
      // to add a new Plotly chart element with the current figure data
      const success = addElement(
        ELEMENT_TYPES.PLOTLY_CHART,
        {
          data: currentFigPayload.data,
          layout: currentFigPayload.layout || {
            title: 'Chart Title',
            showlegend: true,
            autosize: true,
            margin: { l: 50, r: 50, b: 50, t: 50, pad: 4 }
          }
        }
      );
      if (success) {
        // Show notification instead of automatically opening tab
        showNotification = true;
        // Auto-hide notification after 5 seconds
        setTimeout(() => {
          showNotification = false;
        }, 5000);
      }
    }
  };

  const openDashboard = () => {
    window.open('/dashboard', '_blank');
  };

  $: if ($interactionView) {
    const figPayload = $interactionView;
    currentFigPayload = figPayload; // Store current figure for dashboard export
    
    tick().then(() => { // to wait for the DOM to update
      Plotly.newPlot('plotly-figure', figPayload['data'], figPayload['layout'], {
        responsive: true,
      });
      // Add event listener for "plotly_hover" event
      document.getElementById('plotly-figure').addEventListener('plotly_hover', (data) => {
        if (data.points && data.points.length > 0) {
          userActions.set({ type: 'HOVER', payload: data.points[0].data });
        }
      });
    });
  }
  
  const handleMouseEnter = () => {
    isHovered = true;
  };
  
  const handleMouseLeave = () => {
    isHovered = false;
  };
</script>

<div 
  class="relative w-full h-full" 
  on:mouseenter={handleMouseEnter}
  on:mouseleave={handleMouseLeave}
  role="region"
  aria-label="Plot figure container"
>
  <div id="plotly-figure" class="w-full h-full rounded-md"></div>
  
  <!-- {#if isHovered}
    <button class="absolute top-2 right-2 bg-blue-600 hover:bg-blue-700 text-white px-3 py-1 rounded-md shadow-md flex items-center transition-opacity duration-200 z-10"
      on:click={addToDashboard}>
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4 mr-1">
        <path stroke-linecap="round" stroke-linejoin="round" d="M3 8.25V18a2.25 2.25 0 002.25 2.25h13.5A2.25 2.25 0 0021 18V8.25m-18 0V6a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 6v2.25m-18 0h18M5.25 6h.008v.008H5.25V6zM7.5 6h.008v.008H7.5V6zm2.25 0h.008v.008H9.75V6z" />
      </svg>
      Add to Dashboard
    </button>
  {/if} -->
  
  {#if showNotification}
    <div class="absolute bottom-4 left-1/2 transform -translate-x-1/2 bg-green-600 text-white px-4 py-2 rounded-md shadow-md transition-opacity duration-200 flex items-center z-10">
      <span>Added to dashboard!</span>
      <button 
        class="ml-3 underline hover:text-gray-200"
        on:click={openDashboard}
      >
        Open dashboard
      </button>
    </div>
  {/if}
</div>