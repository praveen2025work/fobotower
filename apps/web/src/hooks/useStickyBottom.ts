import { useCallback, useEffect, useRef, useState } from "react";

interface StickyBottomOptions {
  /**
   * Distance from the bottom (px) within which we still consider the user
   * to be "at the bottom" and therefore eligible for auto-follow. Anything
   * larger than this means the user has actively scrolled away.
   */
  threshold?: number;
  /**
   * When false the hook stops auto-following even when the user is at the
   * bottom — used to implement an external Pause toggle.
   */
  enabled?: boolean;
}

interface StickyBottomResult<T extends HTMLElement> {
  /** Attach to the scrollable container. */
  ref: React.RefObject<T>;
  /** True when the next mutation will auto-scroll to the newest line. */
  isAtBottom: boolean;
  /** Force a scroll-to-bottom (e.g. after the user re-enables Pause). */
  scrollToBottom: () => void;
}

/**
 * Sticky-bottom auto-follow used by terminal-style log viewers.
 *
 * Tracks scroll position; flips {@link isAtBottom} false when the user
 * scrolls more than {@link StickyBottomOptions.threshold} pixels above the
 * bottom. Consumers should call {@link scrollToBottom} after appending new
 * content while {@link isAtBottom} is true.
 */
export function useStickyBottom<T extends HTMLElement>(
  options: StickyBottomOptions = {},
): StickyBottomResult<T> {
  const { threshold = 40, enabled = true } = options;
  const ref = useRef<T>(null);
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
