import { useEffect, useState } from "react";

const QUERY = "(max-width: 767px)";

/** True on phone-width screens (below Tailwind's `md`), following resizes and rotation. */
export function useIsPhone(): boolean {
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
