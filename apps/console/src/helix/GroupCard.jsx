import { useState } from 'react';

import { randomId } from '@/lib/uuid';

import { decide } from './api';
import { ErrorNote, StatusPill } from './ui';

/** One proposal group: what the run proposes, its priors, and the sign-off. */
export default function GroupCard({ caseId, group, canDecide, onDecided }) {
  const [comment, setComment] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const f = group.finding ?? {};

  const act = async (action) => {
    setBusy(true);
    setError(null);
    try {
      const res = await decide(caseId, {
        groupId: group.group_id,
        action,
        comment,
        idempotencyKey: randomId(),
      });
      onDecided(res.case);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <article className="rounded-lg border border-gray-200 p-3">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">
          {group.label}{' '}
          <span className="font-normal text-gray-500">· {group.item_ids.length} item(s)</span>
        </h3>
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <span>{f.decided_by}</span>
          <StatusPill value={group.decision?.action ?? f.status} />
        </div>
      </header>
      {f.comment && <p className="mt-2 text-sm">{f.comment}</p>}
      {f.reason && <p className="mt-1 text-xs text-rose-700">Escalated: {f.reason}</p>}
      {group.priors.length > 0 && (
        <p className="mt-1 text-xs text-gray-500">
          Prior approved: “{group.priors[0].comment}” ({group.priors[0].decided_by})
        </p>
      )}
      {group.decision && (
        <p className="mt-2 text-xs text-gray-600">
          {group.decision.action === 'approve' ? 'Approved' : 'Rejected'} by {group.decision.decided_by}
          {group.decision.comment ? `: ${group.decision.comment}` : ''}
        </p>
      )}
      {canDecide && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <input
            aria-label={`Comment on ${group.label}`}
            placeholder="Comment (optional)"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            className="min-w-48 flex-1 rounded border border-gray-300 px-2 py-1 text-sm"
          />
          <button
            type="button"
            disabled={busy}
            onClick={() => act('approve')}
            className="rounded bg-emerald-700 px-3 py-1 text-sm text-white disabled:opacity-50"
          >
            Approve
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => act('reject')}
            className="rounded border border-rose-300 px-3 py-1 text-sm text-rose-700 disabled:opacity-50"
          >
            Reject
          </button>
        </div>
      )}
      {error && (
        <div className="mt-2">
          <ErrorNote error={error} />
        </div>
      )}
    </article>
  );
}
