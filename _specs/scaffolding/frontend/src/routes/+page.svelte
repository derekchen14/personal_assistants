<script lang="ts">
    /**
     * Main application page — connects all stores and renders the full UI.
     *
     * Two phases:
     *   1. Login phase: user enters their name, conversation.connect() is called.
     *   2. Connected phase: three-panel layout (chat | top display | bottom display).
     *
     * Auto-reconnect:
     *   onMount checks for a saved username cookie and reconnects immediately
     *   if found.  The user never sees the login screen on a page reload.
     *
     * Frame routing:
     *   A $effect watches conversation.messages.  When a new agent message
     *   arrives with a frame, setFrame() routes it to topFrame or bottomFrame
     *   based on frame.panel.
     *
     * Ghost creation panel:
     *   When $creatingItem is true, the bottom pane shows an inline creation
     *   form instead of a CardBlock.  The form is entity-specific — branch on
     *   $activePage to show the right input fields.
     *
     * focusEl Svelte action:
     *   Applied to the first input in each ghost form.  tick().then(el.focus())
     *   waits for the DOM to render before focusing, so the user can start
     *   typing immediately without clicking.
     *
     * handleKeydown:
     *   Enter (without Shift) sends the message.
     *   Shift+Enter inserts a newline if using a textarea input.
     *
     * Domain-specific:
     *   - Replace 'AssistantName' with your assistant's name everywhere.
     *   - Update the nav tabs array to match your ActivePage values.
     *   - Update the ghost creation panel to match your entity2/entity3 fields.
     */

    import { conversation, type Message } from '$lib/stores/conversation';
    import {
        setFrame, clearFrames, showPage,
        topFrame, bottomFrame, displayLayout,
        activePage, searchQuery, creatingItem,
        type ActivePage,
    } from '$lib/stores/display';
    import BlockRenderer from '$lib/components/blocks/BlockRenderer.svelte';
    import { tick, onMount } from 'svelte';

    // ── State ──────────────────────────────────────────────────────────────────
    let usernameInput = $state('');
    let messageInput = $state('');
    let chatContainer: HTMLElement | undefined = $state();

    // Ghost creation form fields — one set per entity type
    let newEntity2Text = $state('');
    let newEntity3Name = $state('');
    let newEntity3Definition = $state('');

    // ── focusEl Svelte action ──────────────────────────────────────────────────
    // tick() waits for the DOM to update before focusing.  Without tick(), the
    // element may not exist yet when use:focusEl runs.
    function focusEl(el: HTMLElement) {
        tick().then(() => el.focus());
    }

    // ── Lifecycle ──────────────────────────────────────────────────────────────
    onMount(() => {
        // Auto-reconnect: if a username cookie exists, connect immediately.
        // The user never sees the login screen on a page reload.
        const saved = conversation.savedUsername();
        if (saved && !$conversation.connected) {
            conversation.connect(saved);
        }
    });

    // ── Frame routing ──────────────────────────────────────────────────────────
    // Watch the message list; route new agent frames to the display stores.
    $effect(() => {
        const msgs = $conversation.messages;
        const last = msgs[msgs.length - 1];
        if (last?.frame && last.role === 'agent') {
            setFrame(last.frame as any);
        }
    });

    // Auto-scroll chat panel to the latest message
    $effect(() => {
        $conversation.messages;
        tick().then(() => {
            if (chatContainer) {
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }
        });
    });

    // ── Event handlers ─────────────────────────────────────────────────────────

    function handleConnect() {
        const name = usernameInput.trim();
        if (!name) return;
        conversation.connect(name);
    }

    function handleUsernameKey(e: KeyboardEvent) {
        if (e.key === 'Enter') {
            e.preventDefault();
            handleConnect();
        }
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

    function handleLogout() {
        conversation.disconnect();
        clearFrames();
    }

    function onReset() {
        conversation.reset();
        clearFrames();
    }

    // ── Ghost creation form handlers ───────────────────────────────────────────
    // Called on blur or Enter.  Creates the item via WebSocket and clears the form.

    function handleEntity2Submit() {
        const text = newEntity2Text.trim();
        if (text) {
            conversation.createEntity2(text);
        }
        creatingItem.set(false);
        newEntity2Text = '';
    }

    function handleEntity3Submit() {
        const name = newEntity3Name.trim();
        if (name) {
            conversation.createEntity3(name, newEntity3Definition.trim());
        }
        creatingItem.set(false);
        newEntity3Name = '';
        newEntity3Definition = '';
    }

    // Nav tabs: [activePage value, display label]
    // Domain-specific: update to match your entity tabs.
    const NAV_TABS: [string, string][] = [
        ['entity1s', 'Entity1s'],   // e.g., ['sheets', 'Sheets']
        ['entity2s', 'Entity2s'],   // e.g., ['queries', 'Queries']
        ['entity3s', 'Entity3s'],   // e.g., ['metrics', 'Metrics']
    ];
</script>

{#if !$conversation.connected}
    <!-- ── Login phase ────────────────────────────────────────────────────── -->
    <div class="flex-1 flex items-center justify-center">
        <div class="text-center space-y-6">
            <!-- Domain-specific: replace 'Assistant' with your assistant's name -->
            <h1 class="text-8xl font-medium tracking-tight text-[var(--accent)]"
                style="font-family: var(--font-display)">
                Assistant
            </h1>
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
                    class="px-4 py-2 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white font-medium transition-colors cursor-pointer"
                >
                    Start
                </button>
            </div>
        </div>
    </div>

{:else}
    <!-- ── Connected phase ───────────────────────────────────────────────── -->
    <div class="flex-1 flex flex-col overflow-hidden">

        <!-- Header ──────────────────────────────────────────────────────────── -->
        <div class="relative h-12 flex items-center justify-between px-4 border-b border-[var(--border)] border-t-2 border-t-[var(--secondary)] bg-[var(--surface)] shrink-0">

            <!-- Left: Logo + Name -->
            <div class="flex items-center gap-2">
                <span class="text-3xl font-semibold text-[var(--secondary)]"
                      style="font-family: var(--font-display)">
                    Assistant  <!-- Domain-specific: rename -->
                </span>
            </div>

            <!-- Right: Search + Nav tabs + Logout -->
            <div class="flex items-center gap-4">
                <!-- Search box: value is shared with ListBlock via searchQuery store -->
                <div class="flex items-center gap-1.5 px-2 py-1 rounded border border-[var(--border)] bg-[var(--bg)]">
                    <span class="text-[var(--muted)] text-xs">🔍</span>
                    <input
                        type="text"
                        bind:value={$searchQuery}
                        placeholder="Search"
                        class="w-36 text-xs bg-transparent text-[var(--text)] outline-none placeholder:text-[var(--muted)]"
                    />
                </div>

                <!-- Nav tabs: clicking calls showPage() to atomically set page + clear creatingItem -->
                <nav class="flex items-center gap-3 text-sm">
                    {#each NAV_TABS as [page, label]}
                        <button
                            onclick={() => showPage(page as ActivePage)}
                            class="cursor-pointer transition-colors {$activePage === page
                                ? 'font-medium text-[var(--text)]'
                                : 'text-[var(--muted)] hover:text-[var(--accent)]'}"
                        >
                            {label}
                        </button>
                    {/each}
                </nav>

                <!-- Reset: clears agent history and display frames -->
                <button
                    onclick={onReset}
                    class="px-3 py-1 text-xs rounded border border-[var(--border)] text-[var(--muted)] hover:text-[var(--accent)] hover:border-[var(--accent)] transition-colors cursor-pointer"
                >
                    Reset
                </button>

                <button
                    onclick={handleLogout}
                    class="px-3 py-1 text-xs rounded border border-[var(--border)] text-[var(--muted)] hover:text-[var(--accent)] hover:border-[var(--accent)] transition-colors cursor-pointer"
                >
                    Log out
                </button>
            </div>
        </div>

        <!-- Main content area ────────────────────────────────────────────────── -->
        <div class="flex-1 flex gap-3 overflow-hidden bg-[var(--panel)] p-3">

            <!-- Chat section (1/3 width) ──────────────────────────────────── -->
            <div class="flex flex-col w-1/3 rounded-lg border border-[var(--border)] bg-[var(--surface)]">

                <!-- Messages -->
                <div bind:this={chatContainer} class="flex-1 overflow-y-auto p-4 space-y-3">
                    {#each $conversation.messages as msg (msg.id)}
                        {#if msg.text}
                            <div class="flex" class:justify-end={msg.role === 'user'}>
                                <div class="max-w-[80%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap
                                    {msg.role === 'user'
                                        ? 'bg-[var(--accent-light)]'
                                        : 'bg-[var(--hover)] border border-[var(--border)]'}">
                                    {msg.text}
                                </div>
                            </div>
                        {/if}
                    {/each}

                    <!-- Typing indicator (animated dots) -->
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

                <!-- Message input -->
                <div class="p-4 border-t border-[var(--border)] bg-[var(--bg)] rounded-b-lg">
                    <div class="flex gap-2">
                        <input
                            type="text"
                            bind:value={messageInput}
                            onkeydown={handleKeydown}
                            placeholder="Message Assistant..."
                            class="flex-1 px-4 py-2 rounded-lg bg-[var(--surface)] border border-[var(--border)] text-[var(--text)] outline-none focus:border-[var(--accent)]"
                        />
                        <button
                            onclick={handleSend}
                            class="px-4 py-2 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white font-medium transition-colors cursor-pointer"
                        >
                            Send
                        </button>
                    </div>
                </div>
            </div>

            <!-- Display panel (2/3 width) ─────────────────────────────────── -->
            <div class="flex flex-col flex-1 gap-3">

                <!-- Top container: list/grid frame ──────────────────────── -->
                {#if $displayLayout === 'top' || $displayLayout === 'split'}
                    <div class="flex flex-col grow-[2] h-0 overflow-y-auto p-4 rounded-lg border border-[var(--border)] bg-[var(--surface)]">
                        {#if $topFrame}
                            <BlockRenderer frame={$topFrame} />
                        {/if}
                    </div>
                {/if}

                <!-- Bottom container: card frame or ghost creation panel ── -->
                {#if $displayLayout === 'bottom' || $displayLayout === 'split' || $creatingItem}
                    <div class="flex flex-col grow-[2] h-0 min-h-0 rounded-lg border border-[var(--border)] bg-[var(--surface)]">

                        {#if $creatingItem}
                            <!--
                                Ghost creation panel: shows an inline form for
                                creating a new entity.  Branch on $activePage to
                                show entity2- or entity3-appropriate inputs.

                                use:focusEl on the first input auto-focuses it
                                so the user can start typing immediately.

                                Blur saves and closes the form.
                                Escape cancels without saving.
                            -->
                            <div class="flex flex-col h-full p-6 gap-3">
                                {#if $activePage === 'entity2s'}
                                    <!-- entity2: single textarea (plain text) -->
                                    <textarea
                                        class="flex-1 resize-none bg-transparent border border-[var(--border)] rounded p-2 text-sm text-[var(--text)] outline-none focus:border-[var(--accent)] placeholder:text-[var(--muted)] font-mono"
                                        placeholder="Enter text…"
                                        bind:value={newEntity2Text}
                                        onblur={handleEntity2Submit}
                                        onkeydown={(e) => {
                                            if (e.key === 'Enter' && !e.shiftKey) {
                                                e.preventDefault();
                                                handleEntity2Submit();
                                            } else if (e.key === 'Escape') {
                                                creatingItem.set(false);
                                                newEntity2Text = '';
                                            }
                                        }}
                                        use:focusEl
                                    ></textarea>

                                {:else if $activePage === 'entity3s'}
                                    <!-- entity3: name input + definition textarea -->
                                    <input
                                        class="text-lg font-semibold bg-transparent border-b border-[var(--border)] pb-2 outline-none focus:border-[var(--accent)] text-[var(--text)] placeholder:text-[var(--muted)]"
                                        placeholder="Name"
                                        bind:value={newEntity3Name}
                                        onkeydown={(e) => {
                                            if (e.key === 'Enter') {
                                                e.preventDefault();
                                                handleEntity3Submit();
                                            } else if (e.key === 'Escape') {
                                                creatingItem.set(false);
                                                newEntity3Name = '';
                                                newEntity3Definition = '';
                                            }
                                        }}
                                        use:focusEl
                                    />
                                    <textarea
                                        class="flex-1 resize-none bg-transparent border border-[var(--border)] rounded p-2 text-sm text-[var(--text)] outline-none focus:border-[var(--accent)] placeholder:text-[var(--muted)]"
                                        placeholder="Definition (optional)"
                                        bind:value={newEntity3Definition}
                                        onblur={handleEntity3Submit}
                                        onkeydown={(e) => {
                                            if (e.key === 'Escape') {
                                                creatingItem.set(false);
                                                newEntity3Name = '';
                                                newEntity3Definition = '';
                                            }
                                        }}
                                    ></textarea>
                                {/if}
                                <p class="text-sm text-[var(--muted)] italic">
                                    Press 'Enter' to save, or 'Esc' to cancel.
                                </p>
                            </div>

                        {:else if $bottomFrame}
                            <BlockRenderer frame={$bottomFrame} />

                        {:else}
                            <!-- Empty state placeholder -->
                            <div class="flex items-center justify-center h-full text-[var(--muted)] text-sm">
                                Select an item to view details
                            </div>
                        {/if}

                    </div>
                {/if}
            </div>

        </div>
    </div>
{/if}
