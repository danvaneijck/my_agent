import { useEffect, useRef, useState } from "react";
import { Terminal } from "xterm";
import { FitAddon } from "@xterm/addon-fit";
import { WebLinksAddon } from "@xterm/addon-web-links";
import "xterm/css/xterm.css";
import { getToken } from "@/api/client";

export interface TerminalViewProps {
  taskId: string;
  onClose?: () => void;
}

type ConnectionStatus = "connecting" | "connected" | "disconnected" | "error";

export default function TerminalView({ taskId, onClose }: TerminalViewProps) {
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<Terminal | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const [errorMessage, setErrorMessage] = useState<string>("");

  useEffect(() => {
    if (!terminalRef.current) return;

    // Initialize xterm.js terminal with dark theme
    const term = new Terminal({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      theme: {
        background: "#0d0e14",
        foreground: "#c5c8c6",
        cursor: "#c5c8c6",
        black: "#1d1f21",
        red: "#cc6666",
        green: "#b5bd68",
        yellow: "#f0c674",
        blue: "#81a2be",
        magenta: "#b294bb",
        cyan: "#8abeb7",
        white: "#c5c8c6",
        brightBlack: "#666666",
        brightRed: "#d54e53",
        brightGreen: "#b9ca4a",
        brightYellow: "#e7c547",
        brightBlue: "#7aa6da",
        brightMagenta: "#c397d8",
        brightCyan: "#70c0b1",
        brightWhite: "#eaeaea",
      },
      cols: 80,
      rows: 24,
    });

    // Add addons
    const fitAddon = new FitAddon();
    const webLinksAddon = new WebLinksAddon();
    term.loadAddon(fitAddon);
    term.loadAddon(webLinksAddon);

    // Mount terminal
    term.open(terminalRef.current);
    fitAddon.fit();

    xtermRef.current = term;
    fitAddonRef.current = fitAddon;

    // Connect to WebSocket
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const token = getToken();
    const wsUrl = `${protocol}//${window.location.host}/api/tasks/${taskId}/terminal/ws?token=${encodeURIComponent(token)}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus("connecting");
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);

        if (message.type === "ready") {
          setStatus("connected");
          term.focus();
        } else if (message.type === "output") {
          term.write(message.data);
        } else if (message.type === "error") {
          setStatus("error");
          setErrorMessage(message.message || "Unknown error");
          term.writeln(`\r\n\x1b[31mError: ${message.message}\x1b[0m\r\n`);
        }
      } catch (e) {
        console.error("Failed to parse WebSocket message:", e);
      }
    };

    ws.onerror = () => {
      setStatus("error");
      setErrorMessage("WebSocket connection error");
    };

    ws.onclose = () => {
      setStatus("disconnected");
      term.writeln("\r\n\x1b[33mConnection closed\x1b[0m\r\n");
    };

    // Handle terminal input
    const disposable = term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "input", data }));
      }
    });

    // Handle window resize
    const handleResize = () => {
      fitAddon.fit();
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(
          JSON.stringify({
            type: "resize",
            rows: term.rows,
            cols: term.cols,
          })
        );
      }
    };

    window.addEventListener("resize", handleResize);

    // Cleanup
    return () => {
      window.removeEventListener("resize", handleResize);
      disposable.dispose();
      ws.close();
      term.dispose();
    };
  }, [taskId]);

  const handleReconnect = () => {
    setStatus("connecting");
    setErrorMessage("");
    // Force re-render by closing and reopening
    onClose?.();
  };

  return (
    <div className="flex flex-col h-full bg-[#0d0e14]">
      {/* Status bar */}
      {status !== "connected" && (
        <div
          className={`flex items-center justify-between px-4 py-2 text-sm ${
            status === "connecting"
              ? "bg-yellow-900/20 text-yellow-400"
              : status === "error"
              ? "bg-red-900/20 text-red-400"
              : "bg-gray-800 text-gray-400"
          }`}
        >
          <span>
            {status === "connecting" && "Connecting to terminal..."}
            {status === "error" && `Error: ${errorMessage}`}
            {status === "disconnected" && "Disconnected from terminal"}
          </span>
          {(status === "error" || status === "disconnected") && (
            <button
              onClick={handleReconnect}
              className="px-3 py-1 text-xs bg-accent hover:bg-accent-hover rounded transition-colors"
            >
              Reconnect
            </button>
          )}
        </div>
      )}

      {/* Terminal container */}
      <div ref={terminalRef} className="flex-1 p-2" />
    </div>
  );
}
