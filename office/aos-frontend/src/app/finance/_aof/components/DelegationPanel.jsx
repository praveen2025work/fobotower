// Generated from apps/web/src/components/DelegationPanel.tsx by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see docs/agent-one-finance/office/conversion-guide.md.
// Away? Hand your reviews to a colleague until a date. They decide on your
// behalf — only on capabilities that allow it (review.allow_delegation) and
// within your data scope; both names are recorded on every decision.

import { useState } from "react";
import { UserCheck } from "lucide-react";

import { useDelegate, useDelegations, useDevUsers, useEndDelegation } from "../api/aof";
import { ErrorState, formatTime } from "./ui";

function inDays(n) {
  const d = new Date(Date.now() + n * 86400000);
  return d.toISOString().slice(0, 10);
}

export default function DelegationPanel({ me }) {
  const list = useDelegations();
  const users = useDevUsers();
  const delegate = useDelegate();
  const end = useEndDelegation();
  const [open, setOpen] = useState(false);
  const [toUser, setToUser] = useState("");
  const [until, setUntil] = useState(inDays(5));
  const [reason, setReason] = useState("");
  const away = list.data?.away ?? [];
  const covering = list.data?.covering ?? [];
  const colleagues = (users.data ?? []).filter((u) => u.user_id !== me && u.roles.length > 0);

  return (
    <section className="mt-4 rounded-xl border border-surface-200 bg-card p-4" aria-label="Cover while away">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-surface-900">
          <UserCheck size={15} /> Cover while you are away
        </h2>
        {!open && (
          <button
            onClick={() => setOpen(true)}
            className="rounded-lg border border-surface-300 px-3 py-1 text-xs font-medium text-surface-700 hover:bg-surface-50"
          >
            Hand over my reviews
          </button>
        )}
      </div>
      <p className="mt-1 text-xs text-surface-500">
        A colleague decides on your behalf, only where the capability allows it and only within your data scope. Both
        names are recorded.
      </p>

      {open && (
        <form
          className="mt-3 flex flex-wrap items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            delegate.mutate(
              { toUser, until: new Date(`${until}T23:59:00`).toISOString(), reason },
              {
                onSuccess: () => {
                  setOpen(false);
                  setReason("");
                },
              },
            );
          }}
        >
          <label className="text-xs font-medium text-surface-600">
            Colleague
            {colleagues.length > 0 ? (
              <select
                id="delegate-to"
                required
                value={toUser}
                onChange={(e) => setToUser(e.target.value)}
                className="mt-1 block rounded-lg border border-surface-300 bg-card px-2 py-1.5 text-sm font-normal"
              >
                <option value="" disabled>
                  Choose…
                </option>
                {colleagues.map((u) => (
                  <option key={u.user_id} value={u.user_id}>
                    {u.name ?? u.user_id}
                  </option>
                ))}
              </select>
            ) : (
              <input
                id="delegate-to"
                required
                value={toUser}
                onChange={(e) => setToUser(e.target.value)}
                placeholder="user id"
                className="mt-1 block rounded-lg border border-surface-300 px-2 py-1.5 text-sm font-normal"
              />
            )}
          </label>
          <label className="text-xs font-medium text-surface-600">
            Until
            <input
              id="delegate-until"
              type="date"
              required
              min={inDays(0)}
              max={inDays(60)}
              value={until}
              onChange={(e) => setUntil(e.target.value)}
              className="mt-1 block rounded-lg border border-surface-300 px-2 py-1.5 text-sm font-normal"
            />
          </label>
          <label className="min-w-[12rem] flex-1 text-xs font-medium text-surface-600">
            Reason (optional)
            <input
              id="delegate-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. Annual leave"
              className="mt-1 block w-full rounded-lg border border-surface-300 px-2 py-1.5 text-sm font-normal"
            />
          </label>
          <button
            type="submit"
            disabled={delegate.isPending || !toUser}
            className="rounded-lg bg-brand px-3 py-1.5 text-sm font-medium text-brand-fg hover:bg-brand-strong disabled:opacity-50"
          >
            Hand over
          </button>
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="rounded-lg px-2 py-1.5 text-sm text-surface-600 hover:bg-surface-50"
          >
            Cancel
          </button>
          {delegate.error && (
            <div className="w-full">
              <ErrorState error={delegate.error} />
            </div>
          )}
        </form>
      )}

      {(away.length > 0 || covering.length > 0) && (
        <ul className="mt-3 space-y-1.5 text-xs">
          {away.map((d) => (
            <li key={d.delegation_id} className="flex flex-wrap items-center gap-2">
              <span className="font-medium text-surface-800">{d.to_user}</span> covers for you until{" "}
              {formatTime(d.until)}
              {d.reason && <span className="text-surface-500">({d.reason})</span>}
              {!d.active && (
                <span className="rounded bg-surface-100 px-1.5 text-surface-500">starts {formatTime(d.starts_at)}</span>
              )}
              <button onClick={() => end.mutate(d.delegation_id)} className="text-primary-700 hover:underline">
                End now
              </button>
            </li>
          ))}
          {covering.map((d) => (
            <li key={d.delegation_id} className="text-surface-700">
              You cover for <span className="font-medium">{d.from_user}</span> until {formatTime(d.until)}
              {d.reason && <span className="text-surface-500"> ({d.reason})</span>} — their reviews are in your inbox,
              marked “for {d.from_user}”.
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
