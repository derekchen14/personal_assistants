<script lang="ts">
    let { data }: { data: Record<string, unknown> } = $props();

    let message = $derived((data.message as string) || '');
    let level = $derived((data.level as string) || 'info');

    let borderColor = $derived(
        level === 'error' ? 'border-red-500' :
        level === 'warning' ? 'border-yellow-500' :
        level === 'success' ? 'border-green-500' :
        'border-[var(--color-accent)]'
    );
</script>

<div class="px-4 py-2 rounded-lg border-l-4 {borderColor} bg-[var(--color-surface)] text-sm">
    {message}
</div>
