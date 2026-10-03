import { fetchCase } from './api';
import { Evidence, ItemsTable } from './CaseTables';
import GroupCard from './GroupCard';
import { Empty, ErrorNote, Loading, Panel, StatusPill } from './ui';
import { useAsync } from './useAsync';

// Set in the office to link a case to its trace, e.g.
// https://phoenix.internal/projects/helix/traces/{traceId}
const TRACE_URL = process.env.NEXT_PUBLIC_HELIX_TRACE_URL;

/** One case, entirely as the manifest describes it: proposals, items, evidence. */
export default function CaseDetail({ caseId, onChanged }) {
  const detail = useAsync(() => fetchCase(caseId), [caseId]);

  if (detail.loading && !detail.data) return <Loading what="case" />;
  if (detail.error) return <ErrorNote error={detail.error} />;
  const c = detail.data;

  const onDecided = (updated) => {
    detail.setData(updated);
    onChanged();
  };

  return (
    <div className="space-y-4">
      <Panel
        title={`${c.labels.case}: ${c.subject}`}
        aside={<StatusPill value={c.status} />}
      >
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-600 sm:grid-cols-4">
          <dt className="font-medium">Manifest version</dt>
          <dd>v{c.manifest_version}</dd>
          <dt className="font-medium">Opened by</dt>
          <dd>{c.opened_by}</dd>
          <dt className="font-medium">Trace</dt>
          <dd className="truncate">
            {c.trace_id && TRACE_URL ? (
              <a className="text-blue-700 underline" href={TRACE_URL.replace('{traceId}', c.trace_id)}>
                {c.trace_id.slice(0, 12)}…
              </a>
            ) : (
              c.trace_id ?? 'tracing off'
            )}
          </dd>
        </dl>
        {c.draft && <p className="mt-3 text-sm">{c.draft.headline}</p>}
        {c.error && <p className="mt-2 text-sm text-rose-700">{c.error}</p>}
      </Panel>

      <Panel title="Proposals">
        {c.groups.length === 0 && <Empty>Nothing in scope.</Empty>}
        <div className="space-y-3">
          {c.groups.map((g) => (
            <GroupCard
              key={g.group_id}
              caseId={c.case_id}
              group={g}
              canDecide={c.can_decide && !g.decision}
              onDecided={onDecided}
            />
          ))}
        </div>
      </Panel>

      <ItemsTable label={c.labels.item} columns={c.columns} items={c.items} />
      <Evidence calls={c.tool_calls} />
    </div>
  );
}
