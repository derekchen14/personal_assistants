<script lang="ts">
  import { interactionView } from '@store';
  let content;

  $: if ($interactionView) {
    content = $interactionView['content'];
  }
</script>

<!-- eslint-disable-next-line svelte/no-at-html-tags -->
<p class="text-lg m-10">{@html content}</p>