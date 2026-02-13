<script>
  export let selectedStartDate;
  export let selectedEndDate;

  let selectedQuickRange = 2; // Default to "Past Month"

  const today = new Date();
  const thirtyDaysAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);

  selectedStartDate = selectedStartDate || thirtyDaysAgo.toISOString().split('T')[0];
  selectedEndDate = selectedEndDate || today.toISOString().split('T')[0];

  const quickRanges = [
    { label: 'Past Week', days: 7 },
    { label: 'Past 2 Weeks', days: 14 },
    { label: 'Past Month', days: 30 },
    { label: 'Past 3 Months', days: 90 },
    { label: 'Past Year', days: 365 },
    { label: 'Custom Range', days: null },
  ];

  function setDateRange(days, rangeIndex) {
    selectedQuickRange = rangeIndex;
    
    if (days !== null) {
      const end = new Date();
      const start = new Date();
      start.setDate(start.getDate() - days);
      
      selectedEndDate = end.toISOString().split('T')[0];
      selectedStartDate = start.toISOString().split('T')[0];
    }
  }

  // Clear selected quick range when dates are manually changed
  $: {
    if (selectedQuickRange !== quickRanges.length - 1) { // If not custom range
      const start = new Date(selectedStartDate);
      const end = new Date(selectedEndDate);
      const daysDiff = Math.round((end - start) / (1000 * 60 * 60 * 24));
      
      if (daysDiff !== quickRanges[selectedQuickRange].days) {
        selectedQuickRange = quickRanges.length - 1; // Switch to custom range
      }
    }
  }
</script>

<div class="px-4 mb-4">
  <h4 class="text-sm font-medium text-gray-700 mb-2">Select Date Range:</h4>
  
  <div class="flex flex-wrap gap-2 mb-3">
    {#each quickRanges as range, i}
      <button
        class="px-3 py-1 text-sm rounded-full transition-colors {selectedQuickRange === i ? 
          'bg-blue-500 text-white' : 
          'bg-gray-100 hover:bg-gray-200'}"
        on:click={() => setDateRange(range.days, i)}
      >
        {range.label}
      </button>
    {/each}
  </div>

  {#if selectedQuickRange === quickRanges.length - 1}
    <div class="grid grid-cols-2 gap-4">
      <div>
        <label class="block text-sm text-gray-600 mb-1">Start Date</label>
        <input
          type="date"
          bind:value={selectedStartDate}
          max={selectedEndDate || new Date().toISOString().split('T')[0]}
          class="w-full p-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
        />
      </div>
      <div>
        <label class="block text-sm text-gray-600 mb-1">End Date</label>
        <input
          type="date"
          bind:value={selectedEndDate}
          max={new Date().toISOString().split('T')[0]}
          min={selectedStartDate}
          class="w-full p-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
        />
      </div>
    </div>
  {/if}
</div>
