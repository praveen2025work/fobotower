import clsx from "clsx";
import { useEffect, useState } from "react";
import { Pause, Play } from "lucide-react";
import { useStickyBottom } from "../../hooks/useStickyBottom";

export interface LogLine {
  id: string;
  /** ISO timestamp emitted by the server. */
  ts: string;
  /** info | warn | error | debug */
  level: string;
  /** Originating component (e.g. agent name). */
  source: string;
  message: string;
}

interface LiveTailProps {
  /**
   * Optional injected log feed — used by tests + Storybook. When omitted
   * the component opens an EventSource against the SSE endpoint below.
   */
  feed?: LogLine[];
  /** SSE endpoint; default {@code /api/v1/mission-control/logs/stream}
   * (matches the route published by MissionControlController per PR #85). */
  endpoint?: string;
  /** Cap the number of lines retained in memory. */
  maxLines?: number;
  /** When false the live SSE subscription is skipped (tests). */
  subscribe?: boolean;
}

const LEVEL_CLASS: Record<string, string> = {
  info: "text-accent-300",
  warn: "text-yellow-300",
  warning: "text-yellow-300",
  error: "text-red-300",
  debug: "text-code-muted",
};

function formatTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "--:--:--";
  return d.toISOString().slice(11, 19);
}

/**
 * Right column of Mission Control. Terminal-style log viewer; auto-scrolls
 * to the bottom unless the user has scrolled up >40px or hit Pause.
 */
function LiveTail({
  feed,
  endpoint = "/api/v1/mission-control/logs/stream",
  maxLines = 200,
  subscribe = true,
}: LiveTailProps) {
  const [lines, setLines] = useState<LogLine[]>(feed ?? []);
  const [paused, setPaused] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const { ref, isAtBottom, scrollToBottom } = useStickyBottom<HTMLDivElement>({
    threshold: 40,
    enabled: !paused,
  });

  // External feed wins — useful for tests + previews.
  useEffect(() => {
    if (feed) setLines(feed);
  }, [feed]);

  // Subscribe to the SSE log stream. Skipped when {@code subscribe} is
  // false (tests pass an explicit feed) or in the test environment where
  // EventSource isn't available.
  useEffect(() => {
    if (!subscribe || feed || typeof window === "undefined") return undefined;
    if (typeof window.EventSource === "undefined") return undefined;

    let source: EventSource | null = null;
    try {
      source = new window.EventSource(endpoint, { withCredentials: true });
    } catch (err) {
      setConnectionError(err instanceof Error ? err.message : "stream error");
      return undefined;
    }

    source.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data) as LogLine;
        setLines((prev) => {
          const next = [...prev, parsed];
          return next.length > maxLines ? next.slice(-maxLines) : next;
        });
      } catch {
        // Ignore malformed frames — heartbeats arrive without a JSON body.
      }
    };
    source.onerror = () => {
      setConnectionError("disconnected — retrying");
    };

    return () => {
      source?.close();
    };
  }, [endpoint, feed, subscribe, maxLines]);

  // After every line append, snap to the bottom *if* we're still in
  // sticky-follow mode.
  useEffect(() => {
    if (!paused && isAtBottom) {
      scrollToBottom();
    }
  }, [lines, paused, isAtBottom, scrollToBottom]);

  return (
    <section
      aria-label="Live log tail"
      className="flex h-full flex-col overflow-hidden rounded-xl border border-surface-200 bg-code-bg"
    >
      <header className="flex items-center justify-between border-b border-code-line px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[11px] uppercase tracking-wider text-code-muted">
            Live tail
          </span>
          {connectionError && !feed && (
            <span className="font-mono text-[11px] text-red-300">{connectionError}</span>
          )}
        </div>
        <button
          type="button"
          onClick={() => setPaused((p) => !p)}
          className="inline-flex items-center gap-1 rounded-md border border-code-line px-2 py-0.5 text-[11px] font-medium text-code-fg hover:bg-code-line"
          aria-pressed={paused}
          data-testid="livetail-pause-toggle"
        >
          {paused ? <Play size={12} /> : <Pause size={12} />}
          {paused ? "Resume" : "Pause"}
        </button>
      </header>
      <div
        ref={ref}
        data-testid="livetail-scroller"
        className="flex-1 overflow-y-auto p-2 font-mono text-[11px] leading-relaxed"
      >
        {lines.length === 0 ? (
          <p className="text-code-muted">Waiting for activity…</p>
        ) : (
          lines.map((line) => (
            <div
              key={line.id}
              data-testid="livetail-line"
              className="flex gap-2 whitespace-pre-wrap break-all"
            >
              <span className="shrink-0 text-code-muted">{formatTime(line.ts)}</span>
              <span className="shrink-0 text-code-muted">{line.source}</span>
              <span
                className={clsx(
                  "min-w-0",
                  LEVEL_CLASS[line.level.toLowerCase()] ?? "text-accent-300",
                )}
              >
                {line.message}
              </span>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

export default LiveTail;
