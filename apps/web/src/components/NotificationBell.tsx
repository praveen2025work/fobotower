// The bell: what needs you, and what moved on — the same notifications that go
// to Teams, shown only for cases you may see.

import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import clsx from "clsx";
import { Bell } from "lucide-react";

import { useMarkRead, useNotifications } from "../api/aof";
import { formatTime } from "./ui";

export default function NotificationBell({ enabled = true }: { enabled?: boolean }) {
  const notes = useNotifications(enabled);
  const mark = useMarkRead();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (open && ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const unread = notes.data?.unread ?? 0;
  const items = notes.data?.items ?? [];
  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="relative rounded-lg p-2 text-surface-500 transition-colors hover:bg-surface-100 hover:text-surface-700"
        aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}
      >
        <Bell size={16} />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 min-w-[16px] rounded-full bg-red-600 px-1 text-[10px] font-bold leading-4 text-white">
            {unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-full z-50 mt-1 w-96 rounded-lg border border-surface-200 bg-card shadow-lg" role="dialog" aria-label="Notifications">
          <div className="flex items-center justify-between border-b border-surface-100 px-3 py-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-surface-500">Notifications</span>
            {unread > 0 && (
              <button onClick={() => mark.mutate(null)} className="text-xs text-primary-700 hover:underline">Mark all read</button>
            )}
          </div>
          <ul className="max-h-96 overflow-y-auto">
            {items.length === 0 && <li className="px-3 py-4 text-sm text-surface-400">Nothing yet.</li>}
            {items.map((n) => (
              <li key={n.notification_id}>
                <button
                  onClick={() => {
                    if (!n.read) mark.mutate([n.notification_id]);
                    setOpen(false);
                    if (n.case_id) navigate(`/cases/${encodeURIComponent(n.case_id)}`);
                  }}
                  className={clsx("block w-full border-b border-surface-100 px-3 py-2 text-left hover:bg-surface-50", !n.read && "bg-primary-50/40")}
                >
                  <span className={clsx("block text-sm", n.read ? "text-surface-600" : "font-medium text-surface-900")}>{n.title}</span>
                  {n.body && <span className="mt-0.5 block truncate text-xs text-surface-500">{n.body}</span>}
                  <span className="mt-0.5 block text-[10px] text-surface-400">{formatTime(n.created_at)}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
