<script lang="ts">
    let { size = 24, class: className = '' }: { size?: number; class?: string } = $props();
</script>

<!-- heroicons: bars-arrow-down (outline) -->
<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" width={size} height={size} class={className}>
    <path stroke-linecap="round" stroke-linejoin="round" d="M3 4.5h14.25M3 9h9.75M3 13.5h9.75m4.5-4.5v12m0 0-3.75-3.75M17.25 21l3.75-3.75" />
</svg>
