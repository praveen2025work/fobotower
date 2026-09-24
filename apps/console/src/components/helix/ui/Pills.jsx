import { STATUS, groupOf } from '../constants';

export function GroupPill({ groupKey, short = true, className = '' }) {
  const gp = groupOf(groupKey);
  return (
    <span
      className={`pill shrink-0 ${className}`}
      style={{
        background: gp.bg,
        color: gp.text,
      }}
    >
      {short ? gp.short : gp.label}
    </span>
  );
}

export function StatusPill({ status }) {
  const s = STATUS[status];
  return (
    <span
      className="pill shrink-0 flex items-center gap-1"
      style={{
        background: s.bg,
        color: s.text,
      }}
    >
      <span
        className="w-1.5 h-1.5 rounded-full"
        style={{
          background: s.dot,
        }}
      />
      {status}
    </span>
  );
}

export function DecisionPill({ status }) {
  const st =
    status === 'Pending'
      ? {
          background: 'var(--clr-amber-bg)',
          color: 'var(--clr-amber)',
        }
      : status === 'Rejected'
        ? {
            background: 'var(--clr-red-bg)',
            color: 'var(--clr-red)',
          }
        : {
            background: 'var(--clr-green-bg)',
            color: 'var(--clr-green)',
          };
  return (
    <span className="pill shrink-0" style={st}>
      {status}
    </span>
  );
}

export function Chip({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className="text-xs font-semibold px-3 py-1.5 rounded-full border transition-colors whitespace-nowrap"
      style={
        active
          ? {
              backgroundColor: 'var(--bg-header)',
              borderColor: 'var(--bg-header)',
              color: '#FFFFFF',
            }
          : {
              backgroundColor: 'var(--bg-card-solid)',
              borderColor: 'var(--border)',
              color: 'var(--text-muted)',
            }
      }
    >
      {children}
    </button>
  );
}
