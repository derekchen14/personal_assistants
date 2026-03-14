<script lang="ts">
    import { conversation, type Message } from '$lib/stores/conversation';
    import { setFrame, clearFrames, showPage, topFrame, bottomFrame, displayLayout, activePage, type ActivePage } from '$lib/stores/display';
    import FlowMenu from '$lib/components/FlowMenu.svelte';
    import BlockRenderer from '$lib/components/blocks/BlockRenderer.svelte';
    import { tick, onMount } from 'svelte';

    let usernameInput = $state('');
    let messageInput = $state('');
    let chatContainer: HTMLElement | undefined = $state();
    let sidebarOpen = $state(false);

    onMount(() => {
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
            <h1 class="text-8xl font-medium tracking-tight text-[var(--accent)]" style="font-family: var(--font-display)">Hugo</h1>
            <p class="text-[var(--muted)]">Enter your name to get started</p>
            <div class="flex gap-2">
                <input
                    type="text"
                    bind:value={usernameInput}
                    onkeydown={handleUsernameKey}
                    placeholder="Your name"
                    class="px-4 py-2 rounded-lg bg-[var(--surface)] border border-[var(--border)] text-[var(--text)] outline-none focus:border-[var(--accent)] w-64"
                />
                <button
                    onclick={handleConnect}
                    class="px-4 py-2 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white font-medium transition-colors"
                >
                    Start
                </button>
            </div>
        </div>
    </div>
{:else}
    <!-- Connected layout -->
    <div class="flex-1 flex flex-col overflow-hidden">
        <!-- Global header -->
        <div class="relative h-12 flex items-center justify-between px-4 border-b border-[var(--border)] border-t-2 border-t-[var(--secondary)] bg-[var(--surface)] shrink-0">
            <!-- Left: Logo + Name -->
            <div class="flex items-center gap-2">
                <button
                    onclick={() => sidebarOpen = !sidebarOpen}
                    class="text-3xl cursor-pointer hover:scale-110 transition-transform select-none"
                    title="Open menu"
                >
                    &#x1F4D6;
                </button>
                <span class="text-3xl font-semibold text-[var(--secondary)]" style="font-family: var(--font-display)">
                    Hugo
                </span>
            </div>

            <!-- Right: Entities + Logout -->
            <div class="flex items-center gap-4">
                <nav class="flex items-center gap-3 text-sm">
                    {#each [['posts', 'Posts'], ['drafts', 'Drafts'], ['notes', 'Notes']] as [page, label]}
                        <button
                            onclick={() => showPage(page as ActivePage)}
                            class="cursor-pointer transition-colors {$activePage === page ? 'font-medium hover:text-[var(--accent)]' : 'text-[var(--muted)] hover:text-[var(--accent)]'}"
                        >
                            {label}
                        </button>
                    {/each}
                </nav>
                <button
                    onclick={handleLogout}
                    class="px-3 py-1 text-xs rounded border border-[var(--border)] text-[var(--muted)] hover:text-[var(--accent)] hover:border-[var(--accent)] transition-colors cursor-pointer"
                >
                    Log out
                </button>
            </div>

            <!-- Sidebar (anchored to header) -->
            <FlowMenu onselect={onFlowSelect} onreset={onReset} bind:open={sidebarOpen} />
        </div>

        <!-- Main content area -->
        <div class="flex-1 flex gap-3 overflow-hidden bg-[var(--panel)] p-3">
            <!-- Chat section -->
            <div class="flex flex-col w-1/3 rounded-lg border border-[var(--border)] bg-[var(--surface)]">
                <!-- Messages -->
                <div bind:this={chatContainer} class="flex-1 overflow-y-auto p-4 space-y-3">
                    {#each $conversation.messages as msg (msg.id)}
                        {#if msg.text}
                            <div class="flex" class:justify-end={msg.role === 'user'}>
                                <div
                                    class="max-w-[80%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap {msg.role === 'user' ? 'bg-[var(--accent-light)]' : 'bg-[var(--hover)] border border-[var(--border)]'}"
                                >
                                    {msg.text}
                                </div>
                            </div>
                        {/if}
                    {/each}
                    {#if $conversation.typing}
                        <div class="flex">
                            <div class="px-4 py-2.5 rounded-2xl bg-[var(--hover)] border border-[var(--border)] text-sm text-[var(--muted)]">
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
                <div class="p-4 border-t border-[var(--border)] bg-[var(--bg)] rounded-b-lg">
                    <div class="flex gap-2">
                        <input
                            type="text"
                            bind:value={messageInput}
                            onkeydown={handleKeydown}
                            placeholder="Message Hugo..."
                            class="flex-1 px-4 py-2 rounded-lg bg-[var(--surface)] border border-[var(--border)] text-[var(--text)] outline-none focus:border-[var(--accent)]"
                        />
                        <button
                            onclick={handleSend}
                            class="px-4 py-2 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white font-medium transition-colors"
                        >
                            Send
                        </button>
                    </div>
                </div>
            </div>

            <!-- Display panel -->
            <div class="flex flex-col flex-1 gap-3">
                <!-- Top container (ListBlock) -->
                {#if $displayLayout === 'top' || $displayLayout === 'split'}
                    <div class="flex flex-col grow-[2] h-0 overflow-y-auto p-4 rounded-lg border border-[var(--border)] bg-[var(--surface)]">
                        {#if $topFrame}
                            <BlockRenderer frame={$topFrame} />
                        {/if}
                    </div>
                {/if}

                <!-- Bottom container (CardBlock) -->
                {#if $displayLayout === 'bottom' || $displayLayout === 'split'}
                    <div class="flex flex-col grow-[2] h-0 min-h-0 rounded-lg border border-[var(--border)] bg-[var(--surface)]">
                        {#if $bottomFrame}
                            <BlockRenderer frame={$bottomFrame} />
                        {:else}
                            <div class="flex items-center justify-center h-full text-[var(--muted)] text-sm">
                                Blocks will appear here
                            </div>
                        {/if}
                    </div>
                {/if}
            </div>
        </div>
    </div>
{/if}
