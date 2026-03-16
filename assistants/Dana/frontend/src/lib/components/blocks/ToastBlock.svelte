<script lang="ts">
    let { data }: { data: Record<string, unknown> } = $props();

    let message = $derived((data.message as string) || (data.content as string) || '');
    let level = $derived((data.level as string) || 'info');
    let steps = $derived((data.steps as { name: string; filled: boolean }[]) || []);
    let currentStep = $derived((data.current_step as number) ?? -1);

    let borderColor = $derived(
        level === 'error' ? 'border-red-500' :
        level === 'warning' ? 'border-yellow-500' :
        level === 'success' ? 'border-green-500' :
        'border-[var(--accent)]'
    );
</script>

<div class="px-4 py-3 rounded-lg border-l-4 {borderColor} bg-[var(--surface)] text-sm">
    <p>{message}</p>
    {#if steps.length > 0}
        <div class="flex items-center gap-3 mt-2 pt-2 border-t border-[var(--border)]">
            {#each steps as step, i}
                <div class="flex items-center gap-1.5">
                    <span class="w-2 h-2 rounded-full shrink-0 {step.filled ? 'bg-green-500' : i === currentStep ? 'bg-[var(--accent)]' : 'bg-[var(--border)]'}"></span>
                    <span class="text-xs {step.filled ? 'text-[var(--text)]' : i === currentStep ? 'text-[var(--accent)] font-medium' : 'text-[var(--muted)]'}">
                        {step.name}
                    </span>
                </div>
            {/each}
        </div>
    {/if}
</div>
