<script lang="ts">
    import { conversation } from '$lib/stores/conversation';

    let { data }: { data: Record<string, unknown> } = $props();

    let message = $derived((data.message as string) || 'Are you sure?');
    let confirmLabel = $derived((data.confirm_label as string) || 'Yes');
    let cancelLabel = $derived((data.cancel_label as string) || 'No');

    function respond(choice: string) {
        conversation.send(choice);
    }
</script>

<div class="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4 space-y-3">
    <p class="text-sm">{message}</p>
    <div class="flex gap-2">
        <button
            onclick={() => respond(confirmLabel)}
            class="px-4 py-1.5 rounded bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] text-white text-sm transition-colors"
        >
            {confirmLabel}
        </button>
        <button
            onclick={() => respond(cancelLabel)}
            class="px-4 py-1.5 rounded bg-[var(--color-surface-hover)] hover:bg-[var(--color-border)] text-sm transition-colors"
        >
            {cancelLabel}
        </button>
    </div>
</div>
