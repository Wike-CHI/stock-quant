import { useEffect, useRef, useCallback, useState } from "react";
import { WS_URL } from "../types";

interface UseWSOptions {
  onMessage?: (data: unknown) => void;
  onOpen?: () => void;
  onClose?: () => void;
}

export function useWebSocket(options: UseWSOptions = {}) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const callbacksRef = useRef(options);
  callbacksRef.current = options;

  const connect = useCallback(() => {
    const ws = new WebSocket(WS_URL);
    ws.onopen = () => {
      setConnected(true);
      callbacksRef.current.onOpen?.();
    };
    ws.onclose = () => {
      setConnected(false);
      callbacksRef.current.onClose?.();
      setTimeout(connect, 3000);
    };
    ws.onmessage = (e) => {
      try {
        callbacksRef.current.onMessage?.(JSON.parse(e.data));
      } catch { /* ignore */ }
    };
    wsRef.current = ws;
  }, []);

  useEffect(() => {
    connect();
    return () => wsRef.current?.close();
  }, [connect]);

  const subscribe = useCallback((codes: string[]) => {
    wsRef.current?.send(JSON.stringify({ type: "subscribe", codes }));
  }, []);

  const unsubscribe = useCallback((codes: string[]) => {
    wsRef.current?.send(JSON.stringify({ type: "unsubscribe", codes }));
  }, []);

  return { connected, subscribe, unsubscribe };
}
