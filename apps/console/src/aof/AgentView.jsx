import { useState } from 'react';

import { fetchTasks, openTask } from './api';
import TaskDetail from './TaskDetail';
import { Empty, ErrorNote, Loading, Panel, StatusPill } from './ui';
import { useAsync } from './useAsync';

/** One agent: its tasks, and a form to open a new one from its task key. */
export default function AgentView({ agent }) {
  const tasks = useAsync(() => fetchTasks(agent.id), [agent.id]);
  const [selectedId, setSelectedId] = useState(null);

  const onOpened = (detail) => {
    tasks.reload();
    setSelectedId(detail.task_id);
  };

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">{agent.name}</h2>
        {agent.description && <p className="text-sm text-gray-600">{agent.description}</p>}
        <p className="mt-1 text-xs text-gray-500">Workflow: {agent.steps.join(' → ')}</p>
      </div>

      <OpenTaskForm agent={agent} onOpened={onOpened} />

      <Panel title={`${agent.task_label}s`}>
        {tasks.loading && <Loading what={`${agent.task_label.toLowerCase()}s`} />}
        {tasks.error && <ErrorNote error={tasks.error} />}
        {tasks.data?.length === 0 && (
          <Empty>No {agent.task_label.toLowerCase()}s yet. Open one above.</Empty>
        )}
        {tasks.data?.length > 0 && (
          <ul className="divide-y divide-gray-100">
            {tasks.data.map((c) => (
              <li key={c.task_id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(c.task_id)}
                  aria-current={selectedId === c.task_id ? 'true' : undefined}
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
        <TaskDetail key={selectedId} taskId={selectedId} onChanged={tasks.reload} />
      )}
    </div>
  );
}

function OpenTaskForm({ agent, onOpened }) {
  const [values, setValues] = useState(() =>
    Object.fromEntries(agent.task_key.map((k) => [k, ''])),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onOpened(await openTask(agent.id, values));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel title={`Open a ${agent.task_label.toLowerCase()}`}>
      <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
        {agent.task_key.map((k) => (
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
