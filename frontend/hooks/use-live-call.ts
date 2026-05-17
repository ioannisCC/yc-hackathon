"use client";

import { useEffect, useRef, useState } from "react";
import { callStreamUrl } from "@/lib/api";
import type {
  TranscriptChunk,
  ToolCallRecord,
} from "@/components/dashboard/live-transcript";

export type CallStatus = "in_progress" | "completed" | "failed" | "idle";

export type UseLiveCallResult = {
  chunks: TranscriptChunk[];
  toolCalls: ToolCallRecord[];
  status: CallStatus;
  connected: boolean;
};

/** Subscribes to the SSE stream for a call. Reconnects with exponential
 *  backoff on transport drop. Returns null callId? → idle state with no
 *  connection. */
export function useLiveCall(callId: string | null): UseLiveCallResult {
  const [chunks, setChunks] = useState<TranscriptChunk[]>([]);
  const [toolCalls, setToolCalls] = useState<ToolCallRecord[]>([]);
  const [status, setStatus] = useState<CallStatus>("idle");
  const [connected, setConnected] = useState(false);

  const esRef = useRef<EventSource | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const backoffRef = useRef(500);

  useEffect(() => {
    if (!callId) {
      setStatus("idle");
      setChunks([]);
      setToolCalls([]);
      return;
    }

    let cancelled = false;

    const cleanup = () => {
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };

    const connect = () => {
      if (cancelled) return;
      cleanup();
      const es = new EventSource(callStreamUrl(callId));
      esRef.current = es;

      es.onopen = () => {
        setConnected(true);
        backoffRef.current = 500;
      };

      es.addEventListener("transcript", (e) => {
        try {
          const chunk = JSON.parse((e as MessageEvent).data) as TranscriptChunk;
          setChunks((cur) => [...cur, chunk]);
        } catch {
          /* ignore malformed */
        }
      });

      es.addEventListener("tool_call", (e) => {
        try {
          const tc = JSON.parse((e as MessageEvent).data) as ToolCallRecord;
          setToolCalls((cur) => [...cur, tc]);
        } catch {
          /* ignore */
        }
      });

      es.addEventListener("status", (e) => {
        const data = (e as MessageEvent).data as string;
        if (data === "in_progress" || data === "completed" || data === "failed") {
          setStatus(data);
        }
      });

      es.addEventListener("close", () => {
        setConnected(false);
        cleanup();
      });

      es.onerror = () => {
        setConnected(false);
        cleanup();
        const delay = backoffRef.current;
        backoffRef.current = Math.min(backoffRef.current * 2, 8000);
        reconnectTimerRef.current = setTimeout(() => {
          if (!cancelled) connect();
        }, delay);
      };
    };

    setStatus("in_progress");
    setChunks([]);
    setToolCalls([]);
    connect();

    return () => {
      cancelled = true;
      cleanup();
    };
  }, [callId]);

  return { chunks, toolCalls, status, connected };
}
