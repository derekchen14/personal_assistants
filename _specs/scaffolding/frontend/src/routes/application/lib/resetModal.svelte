<script>
  export let message = '';
  export let onConfirm = () => {};
  export let onCancel = () => {};
</script>

<div class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50">
  <div class="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-md bg-white rounded-lg shadow-lg z-50">
    <div class="p-6">
      <h3 class="text-lg font-semibold text-gray-900 mb-2">Reset Chat</h3>
      <p class="text-gray-600 mb-6">{message}</p>
      
      <div class="flex items-center justify-end space-x-4">
        <button class="px-4 py-2 text-sm text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 transition-colors" on:click={onCancel}>Cancel</button>
        <button class="px-4 py-2 text-sm text-white bg-cyan-600 border border-transparent rounded-md hover:bg-cyan-700 focus:outline-none focus:ring-2 focus:ring-offset-2 transition-colors" on:click={onConfirm}>Confirm</button>
      </div>
    </div>
  </div>
</div>