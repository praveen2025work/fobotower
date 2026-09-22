/**
 * Auto-reconnecting socket keyed by investigation_session_id.
 *
 * All state lives in Postgres, so a reconnect that lands on a different
 * worker loses nothing — the subscription is re-sent and the server reads
 * the thread back from the checkpoint store.
 */
const BASE = process.env.NEXT_PUBLIC_WS_BASE ?? 'ws://localhost:8100';

const INITIAL_RETRY_MS = 500;
const MAX_RETRY_MS = 10000;

export class WebSocketClient {
  constructor(path, { onEvent, onError } = {}) {
    this.url = `${BASE}${path}`;
    this.onEvent = onEvent ?? (() => {});
    this.onError = onError ?? (() => {});
    this.socket = null;
    this.closed = false;
    this.retryMs = INITIAL_RETRY_MS;
    this.pending = [];
  }

  connect() {
    this.socket = new WebSocket(this.url);

    this.socket.onopen = () => {
      this.retryMs = INITIAL_RETRY_MS;
      for (const msg of this.pending.splice(0)) {
        this.socket.send(JSON.stringify(msg));
      }
    };

    this.socket.onmessage = (event) => {
      try {
        this.onEvent(JSON.parse(event.data));
      } catch (err) {
        this.onError(err);
      }
    };

    this.socket.onclose = () => {
      if (this.closed) return;
      setTimeout(() => this.connect(), this.retryMs);
      this.retryMs = Math.min(this.retryMs * 2, MAX_RETRY_MS);
    };

    this.socket.onerror = (err) => this.onError(err);
    return this;
  }

  send(message) {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(message));
    } else {
      this.pending.push(message);
    }
  }

  close() {
    this.closed = true;
    this.socket?.close();
  }
}
