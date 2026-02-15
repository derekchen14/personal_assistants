import { writable } from 'svelte/store';
import { WebSocketManager } from '$lib/utils/websocket';

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
            update((s) => ({ ...s, username, connected: true }));
        },

        send(text: string) {
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

            ws.send({ text: text.trim() });
        },

        disconnect() {
            ws?.disconnect();
            update((s) => ({ ...s, connected: false }));
        },
    };
}

export const conversation = createConversationStore();
