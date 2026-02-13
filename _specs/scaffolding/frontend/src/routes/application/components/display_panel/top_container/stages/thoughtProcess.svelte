<script lang="ts">
  import { interactionView } from '@store';
  let thought;

  $: if ($interactionView) {
    thought = $interactionView['content'];
  }
</script>

<!-- eslint-disable-next-line svelte/no-at-html-tags -->
<p class="text-lg m-10">
  <span class='italic'>Behind the Scenes</span>:
  {@html thought}
</p>