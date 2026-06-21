export type MessageHandler = (data: Record<string, unknown>) => void;
export type StatusHandler = (status: 'connected' | 'disconnected' | 'error', detail?: string) => void;

export class WebSocketManager {
    private ws: WebSocket | null = null;
    private handler: MessageHandler;
    private statusHandler: StatusHandler | null;
    private url: string;
    private pendingMessages: Record<string, unknown>[] = [];

    constructor(url: string, handler: MessageHandler, statusHandler?: StatusHandler) {
        this.url = url;
        this.handler = handler;
        this.statusHandler = statusHandler || null;
    }

    connect() {
        if (typeof window === 'undefined') return;

        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.ws = new WebSocket(`${protocol}//${location.host}${this.url}`);

        this.ws.onopen = () => {
            this.statusHandler?.('connected');
            for (const msg of this.pendingMessages) {
                this.ws!.send(JSON.stringify(msg));
            }
            this.pendingMessages = [];
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handler(data);
            } catch {
                console.error('Failed to parse WebSocket message:', event.data);
            }
        };

        this.ws.onclose = (event) => {
            this.statusHandler?.('disconnected', `code=${event.code}`);
            this.ws = null;
        };

        this.ws.onerror = () => {
            this.statusHandler?.('error', 'WebSocket connection error');
        };
    }

    send(data: Record<string, unknown>) {
        if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        } else if (this.ws?.readyState === WebSocket.CONNECTING) {
            this.pendingMessages.push(data);
        }
    }

    disconnect() {
        this.ws?.close();
        this.ws = null;
    }

    get connected(): boolean {
        return this.ws?.readyState === WebSocket.OPEN;
    }
}
