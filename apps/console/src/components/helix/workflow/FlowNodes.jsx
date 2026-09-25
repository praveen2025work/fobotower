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
  return (
    <>
      <Handle type="target" position={Position.Top} id="top" />
      <button
        type="button"
        aria-label={`Open ${data.label}`}
        onClick={() => data.onSelect?.(id)}
        className="w-full h-full rounded-xl px-3 py-2 flex flex-col gap-1 text-left"
        style={{ ...nodeBase, border: '1px solid var(--border)', pointerEvents: 'auto', cursor: 'pointer' }}
      >
        <div className="text-[14px] font-semibold truncate shrink-0">{data.label}</div>
        <div className="text-[11px] truncate shrink-0" style={{ ...mono, color: 'var(--text-muted)' }}>
          {id}
        </div>
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
  return (
    <>
      <Handle type="target" position={Position.Left} id="left" />
      <button
        type="button"
        aria-label={`Open ${data.label}`}
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
        <div className="text-[11px] mb-0.5 shrink-0" style={{ color: 'var(--text-secondary)' }}>
          Escalate → end
        </div>
        {(data.reasonGroups || []).map((g) => (
          <div
            key={g.source}
            className="text-[10.5px] leading-snug shrink-0"
            style={{ color: 'var(--clr-red)' }}
          >
            <span className="font-semibold">{g.label}:</span>{' '}
            <span style={mono}>{g.reasons.join(', ')}</span>
          </div>
        ))}
      </button>
      <Handle type="source" position={Position.Bottom} id="bottom" />
    </>
  );
}

/** `start` / `end` pills — no interaction, just the shape of the chain. */
export function EdgeMarkerNode({ data, sourceOnly, targetOnly }) {
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
    </>
  );
}

export const StartNode = (props) => <EdgeMarkerNode {...props} sourceOnly />;
export const EndNode = (props) => <EdgeMarkerNode {...props} targetOnly />;
