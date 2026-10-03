import { useState } from 'react';

import { fetchCases, openCase } from './api';
import CaseDetail from './CaseDetail';
import { Empty, ErrorNote, Loading, Panel, StatusPill } from './ui';
import { useAsync } from './useAsync';

/** One capability: its cases, and a form to open a new one from its case key. */
export default function CapabilityView({ capability }) {
  const cases = useAsync(() => fetchCases(capability.id), [capability.id]);
  const [selectedId, setSelectedId] = useState(null);

  const onOpened = (detail) => {
    cases.reload();
    setSelectedId(detail.case_id);
  };

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">{capability.name}</h2>
        {capability.description && <p className="text-sm text-gray-600">{capability.description}</p>}
        <p className="mt-1 text-xs text-gray-500">Workflow: {capability.steps.join(' → ')}</p>
      </div>

      <OpenCaseForm capability={capability} onOpened={onOpened} />

      <Panel title={`${capability.case_label}s`}>
        {cases.loading && <Loading what={`${capability.case_label.toLowerCase()}s`} />}
        {cases.error && <ErrorNote error={cases.error} />}
        {cases.data?.length === 0 && (
          <Empty>No {capability.case_label.toLowerCase()}s yet. Open one above.</Empty>
        )}
        {cases.data?.length > 0 && (
          <ul className="divide-y divide-gray-100">
            {cases.data.map((c) => (
              <li key={c.case_id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(c.case_id)}
                  aria-current={selectedId === c.case_id ? 'true' : undefined}
                  className="flex w-full items-center justify-between gap-2 py-2 text-left text-sm hover:bg-gray-50"
                >
                  <span className="font-medium">{c.subject}</span>
                  <StatusPill value={c.status} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      {selectedId && (
        <CaseDetail key={selectedId} caseId={selectedId} onChanged={cases.reload} />
      )}
    </div>
  );
}

function OpenCaseForm({ capability, onOpened }) {
  const [values, setValues] = useState(() =>
    Object.fromEntries(capability.case_key.map((k) => [k, ''])),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onOpened(await openCase(capability.id, values));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel title={`Open a ${capability.case_label.toLowerCase()}`}>
      <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
        {capability.case_key.map((k) => (
          <label key={k} className="flex flex-col text-xs font-medium text-gray-600">
            {k}
            <input
              required
              value={values[k]}
              onChange={(e) => setValues((v) => ({ ...v, [k]: e.target.value }))}
              className="mt-1 rounded border border-gray-300 px-2 py-1 text-sm font-normal text-gray-900"
            />
          </label>
        ))}
        <button
          type="submit"
          disabled={busy}
          className="rounded bg-[#0b2a5b] px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
        >
          {busy ? 'Running…' : 'Open and run'}
        </button>
      </form>
      {error && (
        <div className="mt-3">
          <ErrorNote error={error} />
        </div>
      )}
    </Panel>
  );
}
