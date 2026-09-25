import { useCallback, useEffect, useState } from 'react';
import { fetchVersionYaml } from '../data/workflowApi';
import { YamlDiff } from './YamlDiff';
import { YamlView } from './YamlView';

const toggleButton = 'text-[11px] font-semibold px-2.5 py-1 rounded-full';
const selected = { background: 'var(--bg-card-solid)', color: 'var(--text-primary)' };
const unselected = { color: 'var(--text-muted)' };

function LoadingOrError({ status, error, onRetry }) {
  if (status === 'error') {
    return (
      <div className="flex items-center gap-3 text-[12px]" style={{ color: 'var(--clr-red)' }}>
        <span role="alert">{error}</span>
        <button
          type="button"
          onClick={onRetry}
          className="px-3 py-1 rounded-full text-[11px] font-semibold"
          style={{ border: '1px solid var(--border)' }}
        >
          Retry
        </button>
      </div>
    );
  }
  return (
    <p className="text-[12px]" style={{ color: 'var(--text-muted)' }}>
      Loading YAML…
    </p>
  );
}

/** The YAML tab's body: the version's own YAML, fetched once when this
 *  mounts (i.e. the first time the tab is opened — VersionTabs keeps this
 *  mounted afterward, so switching tabs never re-fetches it). A draft whose
 *  number differs from the active version also offers a diff against it,
 *  fetched only when that view is chosen. */
export function VersionYaml({ v }) {
  const [own, setOwn] = useState({ status: 'loading' });
  const [active, setActive] = useState({ status: 'idle' });
  const [view, setView] = useState('full');
  const showToggle = v.status === 'draft' && v.number !== v.active_number;

  const loadOwn = useCallback(() => {
    setOwn({ status: 'loading' });
    fetchVersionYaml(v.number)
      .then((text) => setOwn({ status: 'ready', text }))
      .catch((e) => setOwn({ status: 'error', error: e.message }));
  }, [v.number]);

  useEffect(() => {
    loadOwn();
  }, [loadOwn]);

  const loadActive = useCallback(() => {
    setActive({ status: 'loading' });
    fetchVersionYaml(v.active_number)
      .then((text) => setActive({ status: 'ready', text }))
      .catch((e) => setActive({ status: 'error', error: e.message }));
  }, [v.active_number]);

  const openDiff = () => {
    setView('diff');
    if (active.status === 'idle') loadActive();
  };

  let body;
  if (view === 'diff' && showToggle) {
    if (own.status !== 'ready') body = <LoadingOrError {...own} onRetry={loadOwn} />;
    else if (active.status !== 'ready') body = <LoadingOrError {...active} onRetry={loadActive} />;
    else body = <YamlDiff before={active.text} after={own.text} />;
  } else {
    body = own.status === 'ready' ? <YamlView text={own.text} /> : <LoadingOrError {...own} onRetry={loadOwn} />;
  }

  return (
    <div className="flex flex-col gap-2 min-w-0">
      {showToggle && (
        <div
          className="flex items-center gap-1 p-1 rounded-full self-start"
          style={{ background: 'var(--bg-muted)', border: '1px solid var(--border)' }}
        >
          <button type="button" onClick={() => setView('full')} className={toggleButton} style={view === 'full' ? selected : unselected}>
            Full YAML
          </button>
          <button type="button" onClick={openDiff} className={toggleButton} style={view === 'diff' ? selected : unselected}>
            Diff vs active v{v.active_number}
          </button>
        </div>
      )}
      {body}
    </div>
  );
}
