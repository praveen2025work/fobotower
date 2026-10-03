import { downloadYaml } from '../data/workflowApi';
import { manrope } from '../lib/format';
import { StatusChip } from './VersionList';
import { when } from './workflowModel';

const pill = 'text-[12px] font-semibold px-3 py-1.5 rounded-full disabled:opacity-40';

const provenance = (a) =>
  [
    `drafted by ${a.drafted_by}`,
    a.decided_by && `approved by ${a.decided_by}`,
    when(a.decided_at),
    a.note && `“${a.note}”`,
  ]
    .filter(Boolean)
    .join(' · ');

export function ActiveStrip({ overview, canDraft, onNewDraft, onUpload, onShowDrafts }) {
  const { active, pending_drafts: pending, overrides } = overview;
  return (
    <div
      className="rounded-2xl px-4 py-3 flex flex-col gap-2"
      style={{ background: 'var(--bg-card-solid)', border: '1px solid var(--border)', boxShadow: 'var(--card-shadow)' }}
    >
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-[16px] font-extrabold" style={{ ...manrope, color: 'var(--text-primary)' }}>
          Workflow v{active.number}
        </span>
        <StatusChip status="active" />
        <span className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>
          {provenance(active)}
        </span>
        {pending > 0 && (
          <button
            type="button"
            onClick={onShowDrafts}
            className={pill}
            style={{ background: 'var(--clr-amber-bg)', color: 'var(--clr-amber)' }}
          >
            {pending} draft{pending === 1 ? '' : 's'} awaiting approval
          </button>
        )}
        <div className="ml-auto flex gap-2 flex-wrap">
          <button
            type="button"
            onClick={() => downloadYaml(active.number)}
            className={pill}
            style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
          >
            Download YAML
          </button>
          <button
            type="button"
            onClick={onUpload}
            disabled={!canDraft}
            className={pill}
            style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
          >
            Upload YAML
          </button>
          <button
            type="button"
            onClick={onNewDraft}
            disabled={!canDraft}
            title={canDraft ? undefined : 'Only Product Control can draft a change'}
            className={pill}
            style={{ background: 'var(--clr-blue)', color: 'var(--text-on-brand)' }}
          >
            New draft
          </button>
        </div>
      </div>
      {overrides?.reasoner && (
        <div role="status" className="rounded-lg px-3 py-2 text-[12px]" style={{ background: 'var(--clr-amber-bg)', color: 'var(--clr-amber)' }}>
          Reasoner overridden to <code>{overrides.reasoner}</code> on this server by FOBO_REASONER. The
          approved setting is <code>{active.config.settings.reason.reasoner}</code>.
        </div>
      )}
    </div>
  );
}
