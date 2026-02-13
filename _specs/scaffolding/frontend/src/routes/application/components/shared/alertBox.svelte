<script>
  import { alertStore } from '@alert';
  import { Alert } from 'flowbite-svelte';

  let alertState = {};
  alertStore.subscribe((val) => {
    alertState = val;
  });

  function hideAlert() {
    alertStore.update((state) => ({ ...state, show: false }));
  }
</script>

{#if alertState.show}
  <div class="mb-4">
    <Alert color={alertState.color} border dismissable on:close={hideAlert}>
      <span class="font-medium">{alertState.prefix}</span>
      {alertState.message}
    </Alert>
  </div>
{/if}
