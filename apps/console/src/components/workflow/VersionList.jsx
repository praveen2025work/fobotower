import { Chip } from './StepCard';
import { STATUS_TONE } from './workflowModel';

export const StatusChip = ({ status }) => <Chip label={status} tone={STATUS_TONE[status] || 'grey'} />;

export function VersionList({ versions, selected, onSelect }) {
  return (
    <ul aria-label="Workflow versions" className="flex flex-col gap-1">
      {versions.map((v) => (
        <li key={v.number}>
          <button
            type="button"
            onClick={() => onSelect(v.number)}
            aria-current={selected === v.number ? 'true' : undefined}
            className="w-full text-left rounded-lg px-3 py-2"
            style={{
              background: selected === v.number ? 'var(--bg-hover)' : 'transparent',
              border: '1px solid var(--border)',
            }}
          >
            <div className="flex items-center gap-2">
              <span className="text-[13px] font-bold" style={{ color: 'var(--text-primary)' }}>
                v{v.number}
              </span>
              <StatusChip status={v.status} />
              <span className="ml-auto text-[10.5px]" style={{ color: 'var(--text-muted)' }}>
                {v.drafted_by}
              </span>
            </div>
            <div className="text-[11.5px] truncate" style={{ color: 'var(--text-secondary)' }}>
              {v.note}
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
}
