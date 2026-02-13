<script>
  import { onMount } from 'svelte';
  import { utteranceHistory } from '@store';
  import { serverUrl } from '@store';

  onMount(async () => {
    // Get conversation id from the URL
    const conversationId = window.location.pathname.split('/').pop();
    const response = await fetch(`${serverUrl}/conversation/${conversationId}`);
    if (response.ok) {
      const conversationData = await response.json();
      utteranceHistory.set(conversationData.utterances || []);
    } else {
      utteranceHistory.set([]);
    }
  });
</script>