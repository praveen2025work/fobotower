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
        <div className="text-[13px] font-semibold truncate">{data.label}</div>
        <div className="text-[10px] truncate" style={{ ...mono, color: 'var(--text-muted)' }}>
          {id}
        </div>
        <div className="flex flex-wrap gap-1">
          {decidedByChips(data.decidedBy, data.reasoner).map((c) => (
            <Chip key={c.label} {...c} />
          ))}
        </div>
        {data.pausedBefore && (
          <div
            className="text-[10px] font-semibold flex items-center gap-1"
            style={{ color: 'var(--clr-amber)' }}
          >
            ⏸ Pauses before
          </div>
        )}
        {data.canEscalate && (
          <div
            className="text-[10px] flex items-center gap-1"
            style={{ color: 'var(--clr-red)' }}
          >
            <CornerDownRight size={10} /> can escalate
          </div>
        )}
      </button>
      <Handle type="source" position={Position.Bottom} id="bottom" />
      {data.canEscalate && <Handle type="source" position={Position.Right} id="right" />}
    </>
  );
}

/** The `escalate` node: the run's end-of-line when a step can't proceed. */
export function EscalateNode({ id, data }) {
  return (
    <>
      <Handle type="target" position={Position.Left} id="left" />
      <button
        type="button"
        aria-label={`Open ${data.label}`}
        onClick={() => data.onSelect?.(id)}
        className="w-full h-full rounded-xl px-3 py-2 flex flex-col items-center justify-center gap-0.5 text-center"
        style={{
          ...nodeBase,
          border: '1.5px solid var(--clr-red)',
          color: 'var(--clr-red)',
          pointerEvents: 'auto',
          cursor: 'pointer',
        }}
      >
        <div className="text-[13px] font-semibold">{data.label}</div>
        <div className="text-[10.5px]">Escalate → end</div>
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
        className="w-full h-full rounded-full flex items-center justify-center text-[11px] font-semibold"
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
