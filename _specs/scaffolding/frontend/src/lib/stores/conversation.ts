/**
 * Conversation store — WebSocket connection, messages, and all CRUD operations.
 *
 * Architecture:
 *   A single WebSocketManager is created per session (on connect) and torn
 *   down on disconnect.  All panel CRUD operations send silent WS messages
 *   (no chat bubble) and the backend responds with frame updates.
 *
 * Cookie pattern:
 *   The username is saved to a session cookie on connect.  On page reload,
 *   onMount calls savedUsername() and auto-reconnects if a cookie exists.
 *   No login page is needed — just a name input on first visit.
 *
 * Factory function pattern (createConversationStore):
 *   The store is created once at module level and exported as `conversation`.
 *   The factory pattern (instead of a plain object) allows the WebSocketManager
 *   and msgId to be private closure variables, not exposed on the store.
 *
 * CRUD naming convention:
 *   selectEntity*  — sends {select_entity*: id}; triggers card frame response
 *   createEntity*  — sends {create_entity*: true, ...fields}
 *   updateEntity*  — sends {update_entity*: id, ...fields}
 *   deleteEntity*  — sends {delete_entity*: id}
 *
 * Domain-specific: rename entity1/entity2/entity3 to your actual entity names.
 * Add or remove CRUD methods to match your backend's supported operations.
 */

import { writable } from 'svelte/store';
import { WebSocketManager } from '$lib/utils/websocket';

// ── Types ──────────────────────────────────────────────────────────────────

export interface Message {
    id: string;
    role: 'user' | 'agent';
    text: string;
    raw_utterance?: string;
    actions?: unknown[];
    interaction?: Record<string, unknown>;
    code_snippet?: Record<string, unknown> | null;
    frame?: Record<string, unknown> | null;
    timestamp: number;
}

// ── Cookie helpers ─────────────────────────────────────────────────────────
// Kept here (not in a utils file) because they are only used by this store.
// The cookie name should be unique per assistant to avoid collisions when
// running multiple assistants on the same domain.

function getCookie(name: string): string {
    const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    return match ? decodeURIComponent(match[2]) : '';
}

function setCookie(name: string, value: string, days = 30) {
    const expires = new Date(Date.now() + days * 864e5).toUTCString();
    document.cookie = `${name}=${encodeURIComponent(value)};expires=${expires};path=/`;
}

function deleteCookie(name: string) {
    document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/`;
}

// Domain-specific: rename to match your assistant (e.g., 'hugo_username')
const COOKIE_NAME = 'assistant_username';


// ── Store factory ──────────────────────────────────────────────────────────

function createConversationStore() {
    const { subscribe, update } = writable({
        messages: [] as Message[],
        username: '',
        connected: false,
        typing: false,
    });

    let ws: WebSocketManager | null = null;
    let msgId = 0;

    // ── Incoming message handler ───────────────────────────────────────────
    // Called by WebSocketManager for every message from the backend.
    // The frame is stored on the message so +page.svelte's $effect can route
    // it to the correct display store via setFrame().
    function onMessage(data: Record<string, unknown>) {
        if (data.error) {
            console.error('Server error:', data.error);
            return;
        }

        const frame = data.frame as Record<string, unknown> | null;
        if (frame) {
            console.log('[frame] type=%s panel=%s', frame.type, frame.panel);
        }

        const msg: Message = {
            id: `agent-${++msgId}`,
            role: 'agent',
            text: (data.message as string) || '',
            raw_utterance: data.raw_utterance as string,
            actions: data.actions as unknown[],
            interaction: data.interaction as Record<string, unknown>,
            code_snippet: data.code_snippet as Record<string, unknown> | null,
            frame,
            timestamp: Date.now(),
        };

        update((s) => ({
            ...s,
            messages: [...s.messages, msg],
            typing: false,
        }));
    }

    function onStatus(status: string, detail?: string) {
        console.log(`[WS] ${status}${detail ? ': ' + detail : ''}`);
        if (status === 'disconnected' || status === 'error') {
            update((s) => ({ ...s, connected: false, typing: false }));
        }
    }

    return {
        subscribe,

        // ── Connection ─────────────────────────────────────────────────────

        connect(username: string) {
            // WebSocketManager opens the socket; the first message sent is the
            // intro {username} — the backend uses this instead of JWT.
            ws = new WebSocketManager('/api/v1/ws', onMessage, onStatus);
            ws.connect();
            ws.send({ username });
            setCookie(COOKIE_NAME, username);
            update((s) => ({ ...s, username, connected: true }));
        },

        savedUsername(): string {
            // Called in onMount to auto-reconnect on page reload.
            return getCookie(COOKIE_NAME);
        },

        send(text: string) {
            if (!ws?.connected || !text.trim()) return;

            // Add the user message to the conversation immediately (optimistic)
            const msg: Message = {
                id: `user-${++msgId}`,
                role: 'user',
                text: text.trim(),
                timestamp: Date.now(),
            };
            update((s) => ({
                ...s,
                messages: [...s.messages, msg],
                typing: true,
            }));

            ws.send({ text: text.trim() });
        },

        reset() {
            if (!ws?.connected) return;
            ws.send({ reset: true });
            update((s) => ({ ...s, messages: [], typing: false }));
        },

        disconnect() {
            ws?.disconnect();
            ws = null;
            msgId = 0;
            deleteCookie(COOKIE_NAME);
            update(() => ({
                messages: [],
                username: '',
                connected: false,
                typing: false,
            }));
        },

        // ── Entity1 CRUD (read-only: select only) ──────────────────────────
        // entity1 is the read-only entity (e.g., sheets, tables, channels).
        // No create/update/delete because items come from an external source.

        selectEntity1(id: string) {
            // Silent send — no chat bubble; backend responds with card frame
            ws?.send({ select_entity1: id });
        },

        // ── Entity2 CRUD (plain-text editable) ────────────────────────────
        // entity2 is the plain-text entity (e.g., queries, notes).
        // Each item has a single free-text field.

        selectEntity2(id: string) {
            ws?.send({ select_entity2: id });
        },

        createEntity2(text: string) {
            ws?.send({ create_entity2: true, text });
        },

        updateEntity2(id: string, text: string) {
            ws?.send({ update_entity2: id, text });
        },

        deleteEntity2(id: string) {
            ws?.send({ delete_entity2: id });
        },

        // ── Entity3 CRUD (structured: name + definition) ──────────────────
        // entity3 is the structured entity (e.g., metrics, requirements).
        // Each item has a name (short) and a definition (longer description).

        selectEntity3(id: string) {
            ws?.send({ select_entity3: id });
        },

        createEntity3(name: string, definition: string) {
            ws?.send({ create_entity3: true, name, definition });
        },

        updateEntity3(id: string, name: string, definition: string) {
            ws?.send({ update_entity3: id, name, definition });
        },

        deleteEntity3(id: string) {
            ws?.send({ delete_entity3: id });
        },
    };
}

export const conversation = createConversationStore();
