import { useId, useState } from 'react';
import { describeChange } from './workflowModel';
import { VersionYaml } from './VersionYaml';

const tabButton = 'text-[11.5px] font-semibold px-3 py-1 rounded-full';
const selectedTab = { background: 'var(--bg-card-solid)', color: 'var(--text-primary)' };
const unselectedTab = { color: 'var(--text-muted)' };

function Changes({ v }) {
  if (v.number === v.active_number) {
    return (
      <p className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>
        This is the active version.
      </p>
    );
  }
  return (
    <div>
      <h4 className="text-[11px] font-bold uppercase tracking-wide mb-1" style={{ color: 'var(--text-muted)' }}>
        Compared with active v{v.active_number}
      </h4>
      {v.diff.length ? (
        <ul className="list-disc pl-4 text-[12.5px]" style={{ color: 'var(--text-primary)' }}>
          {v.diff.map((c) => (
            <li key={`${c.path}-${c.kind}`}>{describeChange(c)}</li>
          ))}
        </ul>
      ) : (
        <p className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>
          Identical to the active version.
        </p>
      )}
    </div>
  );
}

/** Changes (the readable change list, default) and YAML, for one version's
 *  detail panel. <VersionYaml> mounts the first time its tab opens and stays
 *  mounted — only hidden — after that, so its fetched text survives
 *  switching back to Changes and forth again. A new version replaces this
 *  whole component (VersionDetail's existing reset-on-number-change effect
 *  briefly renders a loading state in its place), which is what puts the
 *  tab back on Changes and drops any YAML it had loaded. */
export function VersionTabs({ v }) {
  const [tab, setTab] = useState('changes');
  const [yamlOpened, setYamlOpened] = useState(false);
  const uid = useId();
  const changesTabId = `${uid}-tab-changes`;
  const yamlTabId = `${uid}-tab-yaml`;
  const changesPanelId = `${uid}-panel-changes`;
  const yamlPanelId = `${uid}-panel-yaml`;

  return (
    <div className="flex flex-col gap-2">
      <div
        role="tablist"
        className="flex gap-1 p-1 rounded-full self-start"
        style={{ background: 'var(--bg-muted)', border: '1px solid var(--border)' }}
      >
        <button
          type="button"
          role="tab"
          id={changesTabId}
          aria-selected={tab === 'changes'}
          aria-controls={changesPanelId}
          onClick={() => setTab('changes')}
          className={tabButton}
          style={tab === 'changes' ? selectedTab : unselectedTab}
        >
          Changes
        </button>
        <button
          type="button"
          role="tab"
          id={yamlTabId}
          aria-selected={tab === 'yaml'}
          aria-controls={yamlPanelId}
          onClick={() => {
            setTab('yaml');
            setYamlOpened(true);
          }}
          className={tabButton}
          style={tab === 'yaml' ? selectedTab : unselectedTab}
        >
          YAML
        </button>
      </div>
      <div
        id={changesPanelId}
        role="tabpanel"
        aria-labelledby={changesTabId}
        style={{ display: tab === 'changes' ? 'block' : 'none' }}
      >
        <Changes v={v} />
      </div>
      {yamlOpened && (
        <div
          id={yamlPanelId}
          role="tabpanel"
          aria-labelledby={yamlTabId}
          style={{ display: tab === 'yaml' ? 'block' : 'none' }}
        >
          <VersionYaml v={v} />
        </div>
      )}
    </div>
  );
}
