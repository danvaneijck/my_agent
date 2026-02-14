import { getToken } from "./client";

export interface WsOptions {
  onMessage: (data: unknown) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (e: Event) => void;
  reconnect?: boolean;
}

export function connectWs(path: string, options: WsOptions): () => void {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const url = `${protocol}//${window.location.host}${path}?token=${encodeURIComponent(getToken())}`;

  let ws: WebSocket | null = null;
  let closed = false;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  function connect() {
    if (closed) return;
    ws = new WebSocket(url);

    ws.onopen = () => options.onOpen?.();

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        options.onMessage(data);
      } catch {
        // ignore non-JSON
      }
    };

    ws.onclose = () => {
      options.onClose?.();
      if (!closed && options.reconnect !== false) {
        reconnectTimer = setTimeout(connect, 3000);
      }
    };

    ws.onerror = (e) => options.onError?.(e);
  }

  connect();

  // Return cleanup function
  return () => {
    closed = true;
    if (reconnectTimer) clearTimeout(reconnectTimer);
    ws?.close();
  };
}

export function sendWsMessage(ws: WebSocket, data: unknown) {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(data));
  }
}
