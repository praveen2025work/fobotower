// Generated from apps/web/src/hooks/useStickyBottom.ts by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see office/README.md.
import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Sticky-bottom auto-follow used by terminal-style log viewers.
 *
 * Tracks scroll position; flips {@link isAtBottom} false when the user
 * scrolls more than {@link StickyBottomOptions.threshold} pixels above the
 * bottom. Consumers should call {@link scrollToBottom} after appending new
 * content while {@link isAtBottom} is true.
 */
export function useStickyBottom(options = {}) {
  const { threshold = 40, enabled = true } = options;
  const ref = useRef(null);
  const [isAtBottom, setIsAtBottom] = useState(true);

  const scrollToBottom = useCallback(() => {
    const node = ref.current;
    if (!node) return;
    node.scrollTop = node.scrollHeight;
  }, []);

  useEffect(() => {
    const node = ref.current;
    if (!node) return undefined;

    const onScroll = () => {
      const distance = node.scrollHeight - node.scrollTop - node.clientHeight;
      setIsAtBottom(distance <= threshold);
    };

    node.addEventListener("scroll", onScroll, { passive: true });
    return () => node.removeEventListener("scroll", onScroll);
  }, [threshold]);

  // Re-scroll any time the consumer marks themselves "at bottom" — mainly
  // important when Pause is toggled back on.
  useEffect(() => {
    if (enabled && isAtBottom) {
      scrollToBottom();
    }
  }, [enabled, isAtBottom, scrollToBottom]);

  return { ref, isAtBottom: enabled && isAtBottom, scrollToBottom };
}
