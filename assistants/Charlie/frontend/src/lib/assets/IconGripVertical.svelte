<script lang="ts">
    let { size = 16, class: className = '' }: { size?: number; class?: string } = $props();
</script>

<!-- 2×3 dot grid — drag handle -->
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 16" width={size} height={size} fill="currentColor" class={className}>
    <circle cx="2.5" cy="2"  r="1.5"/>
    <circle cx="7.5" cy="2"  r="1.5"/>
    <circle cx="2.5" cy="8"  r="1.5"/>
    <circle cx="7.5" cy="8"  r="1.5"/>
    <circle cx="2.5" cy="14" r="1.5"/>
    <circle cx="7.5" cy="14" r="1.5"/>
</svg>
