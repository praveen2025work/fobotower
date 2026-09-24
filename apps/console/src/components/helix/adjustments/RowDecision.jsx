import { Check, X as XIcon } from 'lucide-react';

export function RowDecision({ onApprove, onReject, size = 12 }) {
  return (
    <div className="flex gap-1 shrink-0">
      <button
        onClick={onApprove}
        className="p-1 rounded border border-slate-200 hover:bg-emerald-50"
        style={{
          color: 'var(--clr-green)',
        }}
        aria-label="Approve"
        title="Approve (asks for confirmation)"
      >
        <Check size={size} />
      </button>
      <button
        onClick={onReject}
        className="p-1 rounded border border-slate-200 hover:bg-slate-50"
        style={{
          color: 'var(--text-muted)',
        }}
        aria-label="Reject"
        title="Reject (asks for confirmation)"
      >
        <XIcon size={size} />
      </button>
    </div>
  );
}
