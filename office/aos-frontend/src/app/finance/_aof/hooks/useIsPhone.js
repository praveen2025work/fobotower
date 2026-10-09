// Generated from apps/web/src/hooks/useIsPhone.ts by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see office/README.md.
import { useEffect, useState } from "react";

const QUERY = "(max-width: 767px)";

/** True on phone-width screens (below Tailwind's `md`), following resizes and rotation. */
export function useIsPhone() {
  const get = () => typeof window.matchMedia === "function" && window.matchMedia(QUERY).matches;
  const [phone, setPhone] = useState(get);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia(QUERY);
    const on = () => setPhone(mq.matches);
    mq.addEventListener?.("change", on);
    return () => mq.removeEventListener?.("change", on);
  }, []);
  return phone;
}
