import { useEffect, useRef, useState } from "react";
import { Terminal } from "xterm";
import { FitAddon } from "@xterm/addon-fit";
import { WebLinksAddon } from "@xterm/addon-web-links";
import "xterm/css/xterm.css";
import { getToken } from "@/api/client";
import { Palette } from "lucide-react";
import type { ITheme } from "xterm";

export interface TerminalViewProps {
  taskId: string;
  sessionId: string;
  onClose?: () => void;
}

type ConnectionStatus = "connecting" | "connected" | "disconnected" | "error";

const HISTORY_STORAGE_KEY = "terminal_command_history";
const MAX_HISTORY_SIZE = 100;
const THEME_STORAGE_KEY = "terminal_theme";

// Terminal theme definitions
const THEMES: Record<string, ITheme> = {
  dark: {
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
  light: {
    background: "#fafafa",
    foreground: "#383a42",
    cursor: "#383a42",
    black: "#383a42",
    red: "#e45649",
    green: "#50a14f",
    yellow: "#c18401",
    blue: "#0184bc",
    magenta: "#a626a4",
    cyan: "#0997b3",
    white: "#fafafa",
    brightBlack: "#4f525e",
    brightRed: "#e06c75",
    brightGreen: "#98c379",
    brightYellow: "#e5c07b",
    brightBlue: "#61afef",
    brightMagenta: "#c678dd",
    brightCyan: "#56b6c2",
    brightWhite: "#ffffff",
  },
  monokai: {
    background: "#272822",
    foreground: "#f8f8f2",
    cursor: "#f8f8f0",
    black: "#272822",
    red: "#f92672",
    green: "#a6e22e",
    yellow: "#f4bf75",
    blue: "#66d9ef",
    magenta: "#ae81ff",
    cyan: "#a1efe4",
    white: "#f8f8f2",
    brightBlack: "#75715e",
    brightRed: "#f92672",
    brightGreen: "#a6e22e",
    brightYellow: "#f4bf75",
    brightBlue: "#66d9ef",
    brightMagenta: "#ae81ff",
    brightCyan: "#a1efe4",
    brightWhite: "#f9f8f5",
  },
  dracula: {
    background: "#282a36",
    foreground: "#f8f8f2",
    cursor: "#f8f8f2",
    black: "#21222c",
    red: "#ff5555",
    green: "#50fa7b",
    yellow: "#f1fa8c",
    blue: "#bd93f9",
    magenta: "#ff79c6",
    cyan: "#8be9fd",
    white: "#f8f8f2",
    brightBlack: "#6272a4",
    brightRed: "#ff6e6e",
    brightGreen: "#69ff94",
    brightYellow: "#ffffa5",
    brightBlue: "#d6acff",
    brightMagenta: "#ff92df",
    brightCyan: "#a4ffff",
    brightWhite: "#ffffff",
  },
  solarizedDark: {
    background: "#002b36",
    foreground: "#839496",
    cursor: "#839496",
    black: "#073642",
    red: "#dc322f",
    green: "#859900",
    yellow: "#b58900",
    blue: "#268bd2",
    magenta: "#d33682",
    cyan: "#2aa198",
    white: "#eee8d5",
    brightBlack: "#002b36",
    brightRed: "#cb4b16",
    brightGreen: "#586e75",
    brightYellow: "#657b83",
    brightBlue: "#839496",
    brightMagenta: "#6c71c4",
    brightCyan: "#93a1a1",
    brightWhite: "#fdf6e3",
  },
};

const THEME_LABELS: Record<string, string> = {
  dark: "Dark (Default)",
  light: "Light",
  monokai: "Monokai",
  dracula: "Dracula",
  solarizedDark: "Solarized Dark",
};

export default function TerminalView({ taskId, sessionId, onClose }: TerminalViewProps) {
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<Terminal | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const themePickerRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [showThemePicker, setShowThemePicker] = useState(false);
  const [currentTheme, setCurrentTheme] = useState<string>("dark");

  // Command history management
  const commandHistoryRef = useRef<string[]>([]);
  const historyIndexRef = useRef<number>(-1);
  const currentLineRef = useRef<string>("");

  // Output buffer for rate limiting
  const outputBufferRef = useRef<string[]>([]);
  const flushTimerRef = useRef<number | null>(null);

  // Load theme preference from localStorage on mount
  useEffect(() => {
    try {
      const savedTheme = localStorage.getItem(THEME_STORAGE_KEY);
      if (savedTheme && THEMES[savedTheme]) {
        setCurrentTheme(savedTheme);
      }
    } catch (e) {
      console.error("Failed to load theme preference:", e);
    }
  }, []);

  // Load command history from sessionStorage on mount
  useEffect(() => {
    try {
      const stored = sessionStorage.getItem(HISTORY_STORAGE_KEY);
      if (stored) {
        commandHistoryRef.current = JSON.parse(stored);
      }
    } catch (e) {
      console.error("Failed to load command history:", e);
    }
  }, []);

  // Close theme picker when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        themePickerRef.current &&
        !themePickerRef.current.contains(event.target as Node)
      ) {
        setShowThemePicker(false);
      }
    };

    if (showThemePicker) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [showThemePicker]);

  // Save command to history
  const addToHistory = (command: string) => {
    const trimmed = command.trim();
    if (!trimmed) return;

    // Don't add duplicate consecutive commands
    const last = commandHistoryRef.current[commandHistoryRef.current.length - 1];
    if (last === trimmed) return;

    commandHistoryRef.current.push(trimmed);

    // Keep only last MAX_HISTORY_SIZE commands
    if (commandHistoryRef.current.length > MAX_HISTORY_SIZE) {
      commandHistoryRef.current = commandHistoryRef.current.slice(-MAX_HISTORY_SIZE);
    }

    // Save to sessionStorage
    try {
      sessionStorage.setItem(
        HISTORY_STORAGE_KEY,
        JSON.stringify(commandHistoryRef.current)
      );
    } catch (e) {
      console.error("Failed to save command history:", e);
    }

    // Reset history navigation
    historyIndexRef.current = commandHistoryRef.current.length;
  };

  useEffect(() => {
    if (!terminalRef.current) return;

    // Initialize xterm.js terminal with selected theme
    const term = new Terminal({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      theme: THEMES[currentTheme],
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
    const wsUrl = `${protocol}//${window.location.host}/api/tasks/${taskId}/terminal/ws?token=${encodeURIComponent(token)}&session_id=${encodeURIComponent(sessionId)}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus("connecting");
    };

    // Flush buffered output to terminal
    const flushOutput = () => {
      if (outputBufferRef.current.length > 0 && xtermRef.current) {
        const combined = outputBufferRef.current.join("");
        xtermRef.current.write(combined);
        outputBufferRef.current = [];
      }
      flushTimerRef.current = null;
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);

        if (message.type === "ready") {
          setStatus("connected");
          // Show welcome message
          term.writeln("\x1b[32m✓ Connected to workspace terminal\x1b[0m");
          term.writeln("\x1b[90mTip: Use arrow keys to navigate command history\x1b[0m");
          term.writeln("");
          // Auto-focus terminal on ready
          setTimeout(() => term.focus(), 100);
        } else if (message.type === "output") {
          // Buffer output and flush periodically to prevent UI freezing
          outputBufferRef.current.push(message.data);

          // Flush immediately if buffer is large (>100 chunks)
          if (outputBufferRef.current.length > 100) {
            if (flushTimerRef.current !== null) {
              clearTimeout(flushTimerRef.current);
            }
            flushOutput();
          } else if (flushTimerRef.current === null) {
            // Otherwise flush after 16ms (roughly one frame)
            flushTimerRef.current = window.setTimeout(flushOutput, 16);
          }
        } else if (message.type === "error") {
          setStatus("error");
          setErrorMessage(message.message || "Unknown error");
          term.writeln(`\r\n\x1b[31mError: ${message.message}\x1b[0m\r\n`);
        }
      } catch (e) {
        console.error("Failed to parse WebSocket message:", e);
      }
    };

    ws.onerror = (event) => {
      setStatus("error");
      setErrorMessage("Failed to connect to terminal. The workspace container may not be running.");
      logger.error("terminal_ws_error", event);
    };

    ws.onclose = (event) => {
      setStatus("disconnected");
      const reason = event.code === 1000 ? "Session ended" : "Connection lost";
      term.writeln(`\r\n\x1b[33m${reason}\x1b[0m\r\n`);
      if (event.code !== 1000) {
        setErrorMessage(`Connection closed unexpectedly (code: ${event.code})`);
      }
    };

    // Handle terminal input with command history support
    const disposable = term.onData((data) => {
      if (ws.readyState !== WebSocket.OPEN) return;

      const code = data.charCodeAt(0);

      // Handle special keys
      if (data === "\x1b[A") {
        // Up arrow - previous command
        if (commandHistoryRef.current.length === 0) return;

        if (historyIndexRef.current === commandHistoryRef.current.length) {
          // Save current line before navigating history
          currentLineRef.current = "";
        }

        if (historyIndexRef.current > 0) {
          historyIndexRef.current--;
          const command = commandHistoryRef.current[historyIndexRef.current];

          // Clear current line and write command
          ws.send(
            JSON.stringify({
              type: "input",
              data: "\r\x1b[K" + command,
            })
          );
        }
        return;
      }

      if (data === "\x1b[B") {
        // Down arrow - next command
        if (commandHistoryRef.current.length === 0) return;

        if (
          historyIndexRef.current < commandHistoryRef.current.length - 1
        ) {
          historyIndexRef.current++;
          const command = commandHistoryRef.current[historyIndexRef.current];

          // Clear current line and write command
          ws.send(
            JSON.stringify({
              type: "input",
              data: "\r\x1b[K" + command,
            })
          );
        } else if (historyIndexRef.current === commandHistoryRef.current.length - 1) {
          // At end of history, show saved current line (empty)
          historyIndexRef.current = commandHistoryRef.current.length;
          ws.send(
            JSON.stringify({
              type: "input",
              data: "\r\x1b[K" + currentLineRef.current,
            })
          );
        }
        return;
      }

      // Track Enter key to save commands to history
      if (code === 13) {
        // Enter key
        // Note: We can't reliably extract the command from the terminal,
        // so we just track that a command was sent. The actual command
        // tracking happens on the backend or would require more complex
        // terminal state management.
        historyIndexRef.current = commandHistoryRef.current.length;
        currentLineRef.current = "";
      }

      // Send input to backend
      ws.send(JSON.stringify({ type: "input", data }));
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

      // Clear any pending flush timers
      if (flushTimerRef.current !== null) {
        clearTimeout(flushTimerRef.current);
      }
      outputBufferRef.current = [];
    };
  }, [taskId, sessionId, currentTheme]);

  const handleReconnect = () => {
    setStatus("connecting");
    setErrorMessage("");
    // Close WebSocket if still open
    if (wsRef.current && wsRef.current.readyState !== WebSocket.CLOSED) {
      wsRef.current.close();
    }
    // Trigger re-mount by changing currentTheme temporarily then back
    // This forces the useEffect to re-run and create a new connection
    const theme = currentTheme;
    setCurrentTheme("");
    setTimeout(() => setCurrentTheme(theme), 10);
  };

  const handleChangeTheme = (themeName: string) => {
    setCurrentTheme(themeName);
    setShowThemePicker(false);

    // Save to localStorage
    try {
      localStorage.setItem(THEME_STORAGE_KEY, themeName);
    } catch (e) {
      console.error("Failed to save theme preference:", e);
    }
  };

  // Determine background color based on current theme
  const backgroundColor = THEMES[currentTheme]?.background || "#0d0e14";

  return (
    <div className="flex flex-col h-full relative" style={{ backgroundColor }}>
      {/* Theme picker button */}
      <button
        onClick={() => setShowThemePicker(!showThemePicker)}
        className="absolute top-2 right-2 z-10 p-1.5 rounded bg-surface/80 hover:bg-surface text-gray-400 hover:text-white transition-colors"
        title="Change theme"
      >
        <Palette size={14} />
      </button>

      {/* Theme picker dropdown */}
      {showThemePicker && (
        <div
          ref={themePickerRef}
          className="absolute top-10 right-2 z-20 bg-surface border border-border rounded-md shadow-lg overflow-hidden"
        >
          {Object.entries(THEME_LABELS).map(([key, label]) => (
            <button
              key={key}
              onClick={() => handleChangeTheme(key)}
              className={`w-full px-4 py-2 text-left text-sm transition-colors flex items-center justify-between gap-4 ${
                currentTheme === key
                  ? "bg-accent/20 text-accent-hover"
                  : "text-gray-300 hover:bg-surface-lighter"
              }`}
            >
              <span>{label}</span>
              {currentTheme === key && (
                <span className="text-xs text-accent">✓</span>
              )}
            </button>
          ))}
        </div>
      )}

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
          <span className="flex items-center gap-2">
            {status === "connecting" && (
              <>
                <div className="w-3 h-3 border-2 border-yellow-400 border-t-transparent rounded-full animate-spin" />
                Connecting to terminal...
              </>
            )}
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
