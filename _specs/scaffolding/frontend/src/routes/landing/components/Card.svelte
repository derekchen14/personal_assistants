<script lang="ts">
  import LinkButton from './LinkButton.svelte';

  export let small = 'small_placeholder'
  export let title = 'title_placeholder';
  export let content = 'content_placeholder';
  export let actionText = 'cta_placeholder';
  export let link = 'content_link';
</script>

<div class="w-full md:w-1/3 p-2 lg:p-6 flex flex-col flex-grow flex-shrink">
  <div class="flex flex-wrap no-underline hover:no-underline">
    <div class="flex-1 flex flex-col gap-4 py-4 bg-white rounded-t rounded-b-none overflow-hidden shadow">
      <!-- svelte-ignore a11y-invalid-attribute -->
        <h4 class="w-full title-font text-xl text-gray-800 pt-2 px-6 font-bold">{title}</h4>
        <p class="text-gray-800 text-base px-6">{content}</p>
        <LinkButton secondary path={link}>{actionText}</LinkButton>
    </div>
  </div>
</div>
