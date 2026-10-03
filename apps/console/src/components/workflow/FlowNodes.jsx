import { CornerDownRight } from 'lucide-react';
import { Handle, Position } from '@xyflow/react';
import { mono } from '../lib/format';
import { Chip } from './StepCard';
import { decidedByChips } from './workflowModel';

const nodeBase = {
  background: 'var(--bg-card-solid)',
  boxShadow: 'var(--card-shadow)',
  color: 'var(--text-primary)',
};

/** A `step` node: the label, its mono id, who decides it, and markers for a
 *  pause or an escalation edge leaving it. */
export function StepNode({ id, data }) {
  // aria-label replaces the button's accessible NAME entirely — a screen
  // reader on "Open <label>" would otherwise never hear the decided-by
  // chips, pause or escalate markers a sighted user sees in the node body.
  // aria-describedby points at that same visible content instead of
  // duplicating it into hidden text.
  const descId = `${id}-desc`;
  return (
    <>
      <Handle type="target" position={Position.Top} id="top" />
      <button
        type="button"
        aria-label={`Open ${data.label}`}
        aria-describedby={descId}
        onClick={() => data.onSelect?.(id)}
        className="w-full h-full rounded-xl px-3 py-2 flex flex-col gap-1 text-left"
        style={{ ...nodeBase, border: '1px solid var(--border)', pointerEvents: 'auto', cursor: 'pointer' }}
      >
        <div className="text-[14px] font-semibold truncate shrink-0">{data.label}</div>
        <div className="text-[11px] truncate shrink-0" style={{ ...mono, color: 'var(--text-muted)' }}>
          {id}
        </div>
        <div id={descId} className="contents">
          <div className="flex flex-wrap gap-1 shrink-0">
            {decidedByChips(data.decidedBy, data.reasoner).map((c) => (
              <Chip key={c.label} {...c} size="11px" />
            ))}
          </div>
          {data.pausedBefore && (
            <div
              className="text-[11px] font-semibold flex items-center gap-1 shrink-0"
              style={{ color: 'var(--clr-amber)' }}
            >
              ⏸ Pauses before
            </div>
          )}
          {data.canEscalate && (
            <div
              className="text-[11px] flex items-center gap-1 shrink-0"
              style={{ color: 'var(--clr-red)' }}
            >
              <CornerDownRight size={11} /> can escalate
            </div>
          )}
        </div>
      </button>
      <Handle type="source" position={Position.Bottom} id="bottom" />
      {data.canEscalate && <Handle type="source" position={Position.Right} id="right" />}
    </>
  );
}

/** The `escalate` node: the run's end-of-line when a step can't proceed —
 *  lists the reason codes it can end with, grouped by the step that raises
 *  each one (`data.reasonGroups`, built by `graphLayout.js` from the
 *  graph's own edges). */
export function EscalateNode({ id, data }) {
  const groups = data.reasonGroups || [];
  // Same reasoning as StepNode: aria-label replaces the accessible name, so
  // the reason codes visible in the node body need aria-describedby to
  // reach a screen reader at all.
  const descId = `${id}-desc`;
  return (
    <>
      {/* One target handle per source step, spread down the left edge in
       *  source order — not one handle shared by every incoming edge — so
       *  a later step's shorter hop in can't cross an earlier step's
       *  longer one (which was cutting through its own "if escalated"
       *  label). */}
      {groups.map((g, i) => (
        <Handle
          key={g.source}
          type="target"
          position={Position.Left}
          id={`in-${g.source}`}
          style={{ top: `${((i + 1) / (groups.length + 1)) * 100}%` }}
        />
      ))}
      <button
        type="button"
        aria-label={`Open ${data.label}`}
        aria-describedby={descId}
        onClick={() => data.onSelect?.(id)}
        className="w-full h-full rounded-xl px-3 py-2 flex flex-col gap-1 text-left"
        style={{
          ...nodeBase,
          border: '1.5px solid var(--clr-red)',
          color: 'var(--clr-red)',
          pointerEvents: 'auto',
          cursor: 'pointer',
        }}
      >
        <div className="text-[14px] font-semibold shrink-0">{data.label}</div>
        <div id={descId} className="contents">
          <div className="text-[11px] mb-0.5 shrink-0" style={{ color: 'var(--text-secondary)' }}>
            Escalate → end
          </div>
          {groups.map((g) => (
            <div
              key={g.source}
              className="text-[10.5px] leading-snug shrink-0"
              style={{ color: 'var(--clr-red)' }}
            >
              <span className="font-semibold">{g.label}:</span>{' '}
              <span style={mono}>{g.reasons.join(', ')}</span>
            </div>
          ))}
        </div>
      </button>
      <Handle type="source" position={Position.Bottom} id="bottom" />
    </>
  );
}

/** `start` / `end` pills — no interaction, just the shape of the chain. End
 *  gets a second, right-side target handle (`escalate-in`) distinct from
 *  the chain's own top one, so the escalate→End edge visibly arrives from
 *  its own lane instead of sharing a segment with record→End. */
export function EdgeMarkerNode({ data, sourceOnly, targetOnly, escalateTarget }) {
  return (
    <>
      {!sourceOnly && <Handle type="target" position={Position.Top} id="top" />}
      <div
        className="w-full h-full rounded-full flex items-center justify-center text-[12px] font-semibold"
        style={{ ...nodeBase, border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
      >
        {data.label}
      </div>
      {!targetOnly && <Handle type="source" position={Position.Bottom} id="bottom" />}
      {escalateTarget && <Handle type="target" position={Position.Right} id="escalate-in" />}
    </>
  );
}

export const StartNode = (props) => <EdgeMarkerNode {...props} sourceOnly />;
export const EndNode = (props) => <EdgeMarkerNode {...props} targetOnly escalateTarget />;
