import { writable } from 'svelte/store';
import { WebSocketManager } from '$lib/utils/websocket';
import { activePost } from '$lib/stores/display';

export interface Message {
    id: string;
    role: 'user' | 'agent';
    text: string;
    raw_utterance?: string;
    actions?: unknown[];
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
            // Phase-2 logging: rich frame snapshot to diff against the
            // backend WS-HANDOFF log line. Look for shape mismatches
            // (missing keys, wrong block types, empty data).
            const blocks = (frame.blocks as Array<Record<string, unknown>>) || [];
            console.log('[frame] received:', {
                origin: frame.origin,
                panel: data.panel || frame.panel,
                metadata_keys: Object.keys((frame.metadata as object) || {}),
                blocks: blocks.map((b) => ({
                    type: b.type,
                    data_keys: Object.keys((b.data as object) || {}),
                    location: b.location,
                })),
                msg_len: ((data.message as string) || '').length,
            });
        } else {
            console.log('[frame] none', { msg_len: ((data.message as string) || '').length });
        }

        const msg: Message = {
            id: `agent-${++msgId}`,
            role: 'agent',
            text: (data.message as string) || '',
            raw_utterance: data.raw_utterance as string,
            actions: data.actions as unknown[],
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
            // Recognized payload keys (FE→BE contract, consumed by NLU Phase 1a/1b):
            //   post    — sec_id grounding the utterance to a specific post
            //   section — sec_id grounding to a section within that post
            //   snippet — user-highlighted text inside the post/section
            // Additional keys (e.g. outline Pick's `proposals`) are recognized by
            // `unpack_user_actions` on action-turn dispatch.
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

        action(description: string, dax: string, payload: Record<string, unknown> = {}, pending = false) {
            const body: Record<string, unknown> = { text: `<action>${description}</action>`, dax };
            if (Object.keys(payload).length) body.payload = payload;
            if (pending) update((s) => ({ ...s, typing: true }));
            ws!.send(body);
        },

        refreshPosts(frameType: string = 'list') {
            if (!ws?.connected) return;
            ws.send({ refresh_posts: true, frame_type: frameType });
        },

        selectPost(postId: string) {
            if (!ws?.connected) return;
            activePost.set(postId);
            ws.send({ read_post: postId });
        },

        viewPost(postId: string) {
            if (!ws?.connected) return;
            activePost.set(postId);
            ws.send({ read_post: postId, view: true });
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

        createNote(body: string) {
            if (!ws?.connected) return;
            ws.send({ create_note: true, body });
        },

        updateNote(noteId: string, body: string) {
            if (!ws?.connected) return;
            ws.send({ update_note: noteId, body });
        },

        deleteNote(noteId: string) {
            if (!ws?.connected) return;
            ws.send({ delete_note: noteId });
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
