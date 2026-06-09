"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * useChatStream (Task 37) — consumes the `/api/chat/stream` SSE response.
 *
 * Exposes:
 *   - `status`        the current intermediate status line (paced, see below)
 *   - `streamingText` the reply accumulated so far (token deltas)
 *   - `streaming`     whether a turn is in flight
 *   - `run(body, handlers)` start a streamed turn
 *   - `abort()`       cancel the in-flight turn
 *
 * Status pacing (per the product rule): each status is shown for at least
 * `MIN_STATUS_MS`, so they don't flicker. The moment the reply starts (first
 * `delta`) or finishes (`done`), any pending statuses are skipped — the result
 * preempts the intermediary states.
 */

const MIN_STATUS_MS = 1000;

export type StreamDone = {
  messageId: number | null;
  userMessageId: number | null;
  threadId: string | null;
  text: string;
};

type RunHandlers = {
  onDone?: (d: StreamDone) => void;
  onError?: () => void;
};

type Frame = { event: string | null; data: Record<string, unknown> | null };

function parseFrame(raw: string): Frame {
  let event: string | null = null;
  let dataStr = "";
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataStr += line.slice(5).trim();
  }
  let data: Record<string, unknown> | null = null;
  if (dataStr) {
    try {
      data = JSON.parse(dataStr) as Record<string, unknown>;
    } catch {
      data = null;
    }
  }
  return { event, data };
}

export function useChatStream() {
  const [status, setStatus] = useState<string | null>(null);
  const [streamingText, setStreamingText] = useState("");
  const [streaming, setStreaming] = useState(false);

  const abortRef = useRef<AbortController | null>(null);

  // ── status pacing (refs only, so timer closures never read stale state) ──
  const queueRef = useRef<string[]>([]);
  const shownRef = useRef(false);        // is a status currently on screen?
  const shownAtRef = useRef(0);
  const repliedRef = useRef(false);      // has the reply preempted statuses?
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const showNext = useCallback(() => {
    clearTimer();
    if (repliedRef.current || queueRef.current.length === 0) return;
    const next = queueRef.current.shift() as string;
    shownRef.current = true;
    shownAtRef.current = Date.now();
    setStatus(next);
    if (queueRef.current.length > 0) {
      timerRef.current = setTimeout(showNext, MIN_STATUS_MS);
    }
  }, [clearTimer]);

  const enqueueStatus = useCallback(
    (text: string) => {
      if (repliedRef.current) return;
      queueRef.current.push(text);
      if (timerRef.current !== null) return;       // a pump is already scheduled
      if (!shownRef.current) {
        showNext();                                // nothing shown yet → show now
        return;
      }
      // Wait out the current status's minimum display time, then advance.
      const waited = Date.now() - shownAtRef.current;
      timerRef.current = setTimeout(showNext, Math.max(0, MIN_STATUS_MS - waited));
    },
    [showNext],
  );

  const preempt = useCallback(() => {
    // The reply takes over — skip any remaining intermediary statuses.
    repliedRef.current = true;
    queueRef.current = [];
    shownRef.current = false;
    clearTimer();
    setStatus(null);
  }, [clearTimer]);

  const resetPacing = useCallback(() => {
    queueRef.current = [];
    shownRef.current = false;
    shownAtRef.current = 0;
    repliedRef.current = false;
    clearTimer();
    setStatus(null);
  }, [clearTimer]);

  const abort = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  useEffect(() => () => {
    clearTimer();
    abortRef.current?.abort();
  }, [clearTimer]);

  const run = useCallback(
    async (body: string, handlers: RunHandlers = {}): Promise<void> => {
      abort();
      resetPacing();
      setStreamingText("");
      setStreaming(true);

      const ctrl = new AbortController();
      abortRef.current = ctrl;
      let acc = "";
      let errored = false;

      try {
        const resp = await fetch("/api/chat/stream", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ body }),
          signal: ctrl.signal,
        });

        if (!resp.ok || !resp.body) {
          errored = true;
          return;
        }

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          let sep: number;
          while ((sep = buffer.indexOf("\n\n")) !== -1) {
            const { event, data } = parseFrame(buffer.slice(0, sep));
            buffer = buffer.slice(sep + 2);
            if (!event) continue;

            if (event === "status") {
              const text = (data?.text as string | undefined) ?? "";
              if (text) enqueueStatus(text);
            } else if (event === "delta") {
              preempt();
              acc += (data?.text as string | undefined) ?? "";
              setStreamingText(acc);
            } else if (event === "done") {
              preempt();
              handlers.onDone?.({
                messageId: (data?.message_id as number | null) ?? null,
                userMessageId: (data?.user_message_id as number | null) ?? null,
                threadId: (data?.thread_id as string | null) ?? null,
                text: (data?.text as string | undefined) ?? acc,
              });
            }
          }
        }
      } catch (err) {
        if (!(err instanceof DOMException && err.name === "AbortError")) {
          errored = true;
        }
      } finally {
        clearTimer();
        setStreaming(false);
        setStreamingText("");
        setStatus(null);
        abortRef.current = null;
        if (errored) handlers.onError?.();
      }
    },
    [abort, resetPacing, enqueueStatus, preempt, clearTimer],
  );

  return { status, streamingText, streaming, run, abort };
}
