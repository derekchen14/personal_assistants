<script lang="ts">
    import { conversation, type Message } from '$lib/stores/conversation';
    import { setFrame, topFrame, bottomFrame, displayLayout } from '$lib/stores/display';
    import { layoutMode, type LayoutMode } from '$lib/stores/ui';
    import BlockRenderer from '$lib/components/blocks/BlockRenderer.svelte';
    import { tick } from 'svelte';

    let usernameInput = $state('');
    let messageInput = $state('');
    let chatContainer: HTMLElement | undefined = $state();

    function handleConnect() {
        const name = usernameInput.trim();
        if (!name) return;
        conversation.connect(name);
    }

    function handleSend() {
        const text = messageInput.trim();
        if (!text) return;
        conversation.send(text);
        messageInput = '';
    }

    function handleKeydown(e: KeyboardEvent) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    }

    function handleUsernameKey(e: KeyboardEvent) {
        if (e.key === 'Enter') {
            e.preventDefault();
            handleConnect();
        }
    }

    $effect(() => {
        const msgs = $conversation.messages;
        const last = msgs[msgs.length - 1];
        if (last?.frame && last.role === 'agent') {
            setFrame(last.frame as any);
        }
    });

    // Auto-scroll chat
    $effect(() => {
        $conversation.messages;
        tick().then(() => {
            if (chatContainer) {
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }
        });
    });

    function cycleLayout() {
        layoutMode.update((m) => {
            const modes: LayoutMode[] = ['split', 'top', 'bottom'];
            return modes[(modes.indexOf(m) + 1) % modes.length];
        });
    }
</script>

{#if !$conversation.connected}
    <!-- Username prompt -->
    <div class="flex-1 flex items-center justify-center">
        <div class="text-center space-y-6">
            <h1 class="text-8xl font-medium tracking-tight text-[var(--color-accent)]" style="font-family: var(--font-display)">Hugo</h1>
            <p class="text-[var(--color-text-muted)]">Enter your name to get started</p>
            <div class="flex gap-2">
                <input
                    type="text"
                    bind:value={usernameInput}
                    onkeydown={handleUsernameKey}
                    placeholder="Your name"
                    class="px-4 py-2 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text)] outline-none focus:border-[var(--color-accent)] w-64"
                />
                <button
                    onclick={handleConnect}
                    class="px-4 py-2 rounded-lg bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] text-white font-medium transition-colors"
                >
                    Start
                </button>
            </div>
        </div>
    </div>
{:else}
    <!-- Chat interface -->
    <div class="flex-1 flex gap-3 overflow-hidden">
        <!-- Dialogue panel -->
        {#if $layoutMode !== 'bottom'}
            <div class="flex flex-col {$layoutMode === 'top' ? 'flex-1' : 'w-1/3'}">
                <!-- Header -->
                <div class="h-12 flex items-center justify-between px-4 border-b border-[var(--color-border)] border-t-2 border-t-[var(--color-accent)]">
                    <span class="text-sm font-medium">Hugo</span>
                    <button onclick={cycleLayout} class="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
                        {$layoutMode}
                    </button>
                </div>

                <!-- Messages -->
                <div bind:this={chatContainer} class="flex-1 overflow-y-auto p-4 space-y-3">
                    {#each $conversation.messages as msg (msg.id)}
                        <div class="flex" class:justify-end={msg.role === 'user'}>
                            <div
                                class="max-w-[80%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap {msg.role === 'user' ? 'bg-[var(--color-user-bubble)]' : 'bg-[var(--color-agent-bubble)] border border-[var(--color-border)]'}"
                            >
                                {msg.text}
                            </div>
                        </div>
                    {/each}
                    {#if $conversation.typing}
                        <div class="flex">
                            <div class="px-4 py-2.5 rounded-2xl bg-[var(--color-agent-bubble)] border border-[var(--color-border)] text-sm text-[var(--color-text-muted)]">
                                <span class="inline-flex gap-1">
                                    <span class="animate-bounce" style="animation-delay: 0ms">.</span>
                                    <span class="animate-bounce" style="animation-delay: 150ms">.</span>
                                    <span class="animate-bounce" style="animation-delay: 300ms">.</span>
                                </span>
                            </div>
                        </div>
                    {/if}
                </div>

                <!-- Input -->
                <div class="p-4 border-t border-[var(--color-border)]">
                    <div class="flex gap-2">
                        <input
                            type="text"
                            bind:value={messageInput}
                            onkeydown={handleKeydown}
                            placeholder="Message Hugo..."
                            class="flex-1 px-4 py-2 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text)] outline-none focus:border-[var(--color-accent)]"
                        />
                        <button
                            onclick={handleSend}
                            class="px-4 py-2 rounded-lg bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] text-white font-medium transition-colors"
                        >
                            Send
                        </button>
                    </div>
                </div>
            </div>
        {/if}

        <!-- Display panel -->
        {#if $layoutMode !== 'top'}
            <div class="flex flex-col flex-1 bg-[var(--color-display-bg)] rounded-lg">
                <!-- Top container -->
                {#if $displayLayout === 'top' || $displayLayout === 'split'}
                    <div class="flex flex-col grow-[2] h-0 overflow-y-auto p-4">
                        {#if $topFrame}
                            <BlockRenderer frame={$topFrame} />
                        {/if}
                    </div>
                {/if}

                {#if $displayLayout === 'split'}
                    <div class="border-t border-[var(--color-border)]"></div>
                {/if}

                <!-- Bottom container -->
                {#if $displayLayout === 'bottom' || $displayLayout === 'split'}
                    <div class="flex flex-col grow-[2] h-0 overflow-y-auto p-4">
                        {#if $bottomFrame}
                            <BlockRenderer frame={$bottomFrame} />
                        {:else}
                            <div class="flex items-center justify-center h-full text-[var(--color-text-muted)] text-sm">
                                Blocks will appear here
                            </div>
                        {/if}
                    </div>
                {/if}
            </div>
        {/if}
    </div>
{/if}
