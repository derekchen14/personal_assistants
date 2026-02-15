<script lang="ts">
    import '../app.css';
    let { children } = $props();
</script>

<svelte:head>
    <title>Hugo</title>
</svelte:head>

<div class="h-screen flex flex-col">
    {@render children()}
</div>
