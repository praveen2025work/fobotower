import { ChevronLeft, ChevronRight, CornerDownRight, Lock, Minus } from 'lucide-react';
import { mono } from '../lib/format';
import { TAG_STYLE, decidedByChips } from './workflowModel';

function IconButton({ label, disabled, onClick, children }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className="p-1 rounded disabled:opacity-30 hover:opacity-80"
      style={{ background: 'var(--bg-muted)', color: 'var(--text-secondary)' }}
    >
      {children}
    </button>
  );
}

export function Chip({ label, tone }) {
  const t = TAG_STYLE[tone] || TAG_STYLE.grey;
  return (
    <span
      className="text-[10px] px-1.5 py-0.5 rounded font-semibold whitespace-nowrap"
      style={{ background: t.bg, color: t.fg }}
    >
      {label}
    </span>
  );
}

export function StepCard({
  step,
  index,
  total,
  reasoner,
  errors = [],
  editing = false,
  onSelect,
  onMove,
  onRemove,
}) {
  return (
    <div
      data-testid="step-card"
      data-step={step.name}
      className="rounded-xl px-3 py-2.5 flex flex-col gap-1.5 w-full md:w-[172px]"
      style={{
        background: 'var(--bg-card-solid)',
        border: `1px solid ${errors.length ? 'var(--clr-red)' : 'var(--border)'}`,
        boxShadow: 'var(--card-shadow)',
      }}
    >
      <button
        type="button"
        onClick={() => onSelect(step.name)}
        className="text-left"
        aria-label={`Open ${step.label}`}
      >
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] tabular-nums" style={{ color: 'var(--text-muted)' }}>
            {index + 1}
          </span>
          <span
            className="text-[13px] font-semibold truncate"
            style={{ color: 'var(--text-primary)' }}
          >
            {step.label}
          </span>
          {!step.removable && (
            <span
              role="img"
              aria-label={`Cannot be removed: ${step.required_because}`}
              title={`Cannot be removed: ${step.required_because}`}
              style={{ color: 'var(--text-muted)' }}
            >
              <Lock size={11} />
            </span>
          )}
        </div>
        <div className="text-[10px]" style={{ ...mono, color: 'var(--text-muted)' }}>
          {step.name}
        </div>
      </button>
      <div className="flex flex-wrap gap-1">
        {decidedByChips(step.decided_by, reasoner).map((c) => (
          <Chip key={c.label} {...c} />
        ))}
      </div>
      {step.unknown && (
        <div className="text-[10.5px]" style={{ color: 'var(--clr-red)' }}>
          Not a known step
        </div>
      )}
      {step.can_escalate && (
        <div className="text-[10px] flex items-center gap-1" style={{ color: 'var(--clr-red)' }}>
          <CornerDownRight size={10} /> can escalate → end
        </div>
      )}
      {errors.map((e) => (
        <div key={e} role="alert" className="text-[10.5px]" style={{ color: 'var(--clr-red)' }}>
          {e}
        </div>
      ))}
      {editing && (
        <div className="flex gap-1 pt-1.5" style={{ borderTop: '1px solid var(--border)' }}>
          <IconButton
            label={`Move ${step.name} earlier`}
            disabled={index === 0}
            onClick={() => onMove(index, -1)}
          >
            <ChevronLeft size={12} />
          </IconButton>
          <IconButton
            label={`Move ${step.name} later`}
            disabled={index === total - 1}
            onClick={() => onMove(index, 1)}
          >
            <ChevronRight size={12} />
          </IconButton>
          {step.removable && (
            <IconButton label={`Remove ${step.name}`} onClick={() => onRemove(step.name)}>
              <Minus size={12} />
            </IconButton>
          )}
        </div>
      )}
    </div>
  );
}
