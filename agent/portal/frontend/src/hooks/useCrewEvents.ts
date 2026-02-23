import { useState, useEffect, useRef, useCallback } from "react";
import { connectWs } from "@/api/websocket";
import type { CrewEvent } from "@/types";

export function useCrewEvents(sessionId: string | undefined) {
  const [events, setEvents] = useState<CrewEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const cleanupRef = useRef<(() => void) | null>(null);

  const clear = useCallback(() => setEvents([]), []);

  useEffect(() => {
    if (!sessionId) return;

    cleanupRef.current = connectWs(`/ws/crews/${sessionId}`, {
      onMessage: (data) => {
        setEvents((prev) => [...prev, data as CrewEvent]);
      },
      onOpen: () => setConnected(true),
      onClose: () => setConnected(false),
      reconnect: true,
    });

    return () => {
      cleanupRef.current?.();
      cleanupRef.current = null;
    };
  }, [sessionId]);

  return { events, connected, clear };
}
