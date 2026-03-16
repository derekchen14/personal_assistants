import { writable } from 'svelte/store';
import { WebSocketManager } from '$lib/utils/websocket';
import { activePost } from '$lib/stores/display';

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

function createConversationStore() {
    const { subscribe, update } = writable({
        messages: [] as Message[],
        username: '',
        connected: false,
        typing: false,
    });

    let ws: WebSocketManager | null = null;
    let msgId = 0;

    function onMessage(data: Record<string, unknown>) {
        if (data.error) {
            console.error('Server error:', data.error);
            return;
        }

        const frame = data.frame as Record<string, unknown> | null;
        if (frame) {
            console.log('[frame] received:', frame.type, 'panel:', frame.panel, 'data:', frame.data);
        } else {
            console.log('[frame] none');
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

        connect(username: string) {
            ws = new WebSocketManager('/api/v1/ws', onMessage, onStatus);
            ws.connect();
            ws.send({ username });
            setCookie('hugo_username', username);
            update((s) => ({ ...s, username, connected: true }));
        },

        savedUsername(): string {
            return getCookie('hugo_username');
        },

        send(text: string, dax: string | null = null, payload: Record<string, string> = {}) {
            if (!ws?.connected || !text.trim()) return;

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

            const body: Record<string, unknown> = { text: text.trim() };
            if (dax) body.dax = dax;
            if (Object.keys(payload).length) body.payload = payload;
            ws.send(body);
        },

        action(description: string, dax: string, payload: Record<string, string> = {}) {
            const body: Record<string, unknown> = { text: `<action>${description}</action>`, dax };
            if (Object.keys(payload).length) body.payload = payload;
            ws!.send(body);
        },

        selectPost(postId: string) {
            if (!ws?.connected) return;
            activePost.set(postId);
            ws.send({ select_post: postId });
        },

        viewPost(postId: string) {
            activePost.set(postId);
            this.action(`view post ${postId}`, '{1AD}', { source: postId });
        },

        createPost(type: 'draft' | 'note', title = '', body = '') {
            if (!ws?.connected) return;
            const msg: Record<string, unknown> = { create_post: type };
            if (title) msg.title = title;
            if (body) msg.body = body;
            ws.send(msg);
        },

        deletePost(postId: string) {
            if (!ws?.connected) return;
            ws.send({ delete_post: postId });
        },

        updatePost(postId: string, updates: Record<string, unknown>) {
            if (!ws?.connected) return;
            ws.send({ update_post: postId, updates });
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
            deleteCookie('hugo_username');
            update(() => ({
                messages: [],
                username: '',
                connected: false,
                typing: false,
            }));
        },
    };
}

export const conversation = createConversationStore();
