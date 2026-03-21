<script lang="ts">
    import { conversation, type Message } from '$lib/stores/conversation';
    import { setFrame, clearFrames, showPage, topFrame, bottomFrame, displayLayout, activePage, searchQuery, creatingItem, initTheme, type ActivePage } from '$lib/stores/display';
    import FlowMenu from '$lib/components/FlowMenu.svelte';
    import BlockRenderer from '$lib/components/blocks/BlockRenderer.svelte';
    import { MagnifyingGlass } from '$lib/components/icons';
    import { tick, onMount } from 'svelte';

    let usernameInput = $state('');
    let messageInput = $state('');
    let chatContainer: HTMLElement | undefined = $state();
    let newItemText = $state('');
    let newToolName = $state('');
    let newToolDescription = $state('');

    function focusEl(el: HTMLElement) {
        tick().then(() => el.focus());
    }

    onMount(() => {
        initTheme();
        const saved = conversation.savedUsername();
        if (saved && !$conversation.connected) {
            conversation.connect(saved);
        }
    });

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

    function onFlowSelect(dax: string) {
        messageInput = `/${dax} ${messageInput}`;
    }

    function onReset() {
        conversation.reset();
        clearFrames();
    }

    function handleLogout() {
        conversation.disconnect();
        clearFrames();
    }

    function handleRequirementSubmit() {
        const text = newItemText.trim();
        if (text) {
            conversation.createRequirement(text);
        }
        creatingItem.set(false);
        newItemText = '';
    }

    function handleToolSubmit() {
        const name = newToolName.trim();
        if (name) {
            conversation.createTool(name, newToolDescription.trim());
        }
        creatingItem.set(false);
        newToolName = '';
        newToolDescription = '';
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
</script>

{#if !$conversation.connected}
    <!-- Username prompt -->
    <div class="flex-1 flex items-center justify-center">
        <div class="text-center space-y-6">
            <h1 class="text-8xl font-bold tracking-tight text-[var(--color-accent)]">Kalli</h1>
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
    <div class="flex-1 flex flex-col overflow-hidden">
        <!-- Global header -->
        <div class="h-12 flex items-center justify-between px-4 border-b border-[var(--color-border)] border-t-2 border-t-[var(--color-secondary)] shrink-0">
            <span class="text-lg font-medium text-[var(--color-secondary)]" style="font-family: var(--font-display)">Kalli</span>
            <div class="flex items-center gap-4">
                <div class="flex items-center gap-1.5 px-2 py-1 rounded border border-[var(--color-border)] bg-[var(--color-bg)]">
                    <MagnifyingGlass size={14} class="text-[var(--color-text-muted)]" />
                    <input
                        type="text"
                        bind:value={$searchQuery}
                        placeholder="Search"
                        class="w-28 text-xs bg-transparent text-[var(--color-text)] outline-none placeholder:text-[var(--color-text-muted)]"
                    />
                </div>
                <nav class="flex items-center gap-3 text-sm">
                    {#each [['assistants', 'Assistants'], ['requirements', 'Requirements'], ['tools', 'Tools']] as [page, label]}
                        <button
                            onclick={() => showPage(page as ActivePage)}
                            class="cursor-pointer transition-colors {$activePage === page ? 'font-medium text-[var(--color-text)]' : 'text-[var(--color-text-muted)] hover:text-[var(--color-accent)]'}"
                        >
                            {label}
                        </button>
                    {/each}
                </nav>
                <FlowMenu onselect={onFlowSelect} onreset={onReset} />
                <button
                    onclick={handleLogout}
                    class="px-3 py-1 text-xs rounded border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:border-[var(--color-accent)] transition-colors cursor-pointer"
                >
                    Log out
                </button>
            </div>
        </div>

        <!-- Main content area -->
        <div class="flex-1 flex gap-3 overflow-hidden p-3">
            <!-- Dialogue panel -->
            <div class="flex flex-col w-1/3 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]">
                <!-- Messages -->
                <div bind:this={chatContainer} class="flex-1 overflow-y-auto p-4 space-y-3">
                    {#each $conversation.messages as msg (msg.id)}
                        {#if msg.text}
                            <div class="flex" class:justify-end={msg.role === 'user'}>
                                <div
                                    class="max-w-[80%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap {msg.role === 'user' ? 'bg-[var(--color-user-bubble)]' : 'bg-[var(--color-agent-bubble)] border border-[var(--color-border)]'}"
                                >
                                    {msg.text}
                                </div>
                            </div>
                        {/if}
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
                            placeholder="Message Kalli..."
                            class="flex-1 px-4 py-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] outline-none focus:border-[var(--color-accent)]"
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

            <!-- Display panel -->
            <div class="flex flex-col flex-1 gap-3">
                <!-- Top container -->
                {#if $displayLayout === 'top' || $displayLayout === 'split'}
                    <div class="flex flex-col grow-[2] h-0 overflow-y-auto p-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]">
                        {#if $topFrame}
                            <BlockRenderer frame={$topFrame} />
                        {/if}
                    </div>
                {/if}

                <!-- Bottom container -->
                {#if $displayLayout === 'bottom' || $displayLayout === 'split' || $creatingItem}
                    <div class="flex flex-col grow-[2] h-0 min-h-0 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]">
                        {#if $creatingItem}
                            <div class="flex flex-col h-full p-6 gap-3">
                                {#if $activePage === 'requirements'}
                                    <textarea
                                        class="flex-1 resize-none bg-transparent border border-[var(--color-border)] rounded p-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-accent)] placeholder:text-[var(--color-text-muted)]"
                                        placeholder="Describe a requirement…"
                                        bind:value={newItemText}
                                        onblur={handleRequirementSubmit}
                                        onkeydown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleRequirementSubmit(); } else if (e.key === 'Escape') { creatingItem.set(false); newItemText = ''; } }}
                                        use:focusEl
                                    ></textarea>
                                {:else if $activePage === 'tools'}
                                    <input
                                        class="text-lg font-semibold bg-transparent border-b border-[var(--color-border)] pb-2 outline-none focus:border-[var(--color-accent)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)]"
                                        placeholder="Tool name"
                                        bind:value={newToolName}
                                        onkeydown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleToolSubmit(); } else if (e.key === 'Escape') { creatingItem.set(false); newToolName = ''; newToolDescription = ''; } }}
                                        use:focusEl
                                    />
                                    <textarea
                                        class="flex-1 resize-none bg-transparent border border-[var(--color-border)] rounded p-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-accent)] placeholder:text-[var(--color-text-muted)]"
                                        placeholder="Description (optional)"
                                        bind:value={newToolDescription}
                                        onblur={handleToolSubmit}
                                        onkeydown={(e) => { if (e.key === 'Escape') { creatingItem.set(false); newToolName = ''; newToolDescription = ''; } }}
                                    ></textarea>
                                {/if}
                                <p class="text-sm text-[var(--color-text-muted)] italic">Press 'Enter' to save, or 'Esc' to cancel.</p>
                            </div>
                        {:else if $bottomFrame}
                            <BlockRenderer frame={$bottomFrame} />
                        {:else}
                            <div class="flex items-center justify-center h-full text-[var(--color-text-muted)] text-sm">
                                Blocks will appear here
                            </div>
                        {/if}
                    </div>
                {/if}
            </div>
        </div>
    </div>
{/if}
