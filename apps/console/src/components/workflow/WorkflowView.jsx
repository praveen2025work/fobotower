import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchGraph, fetchVersions, fetchWorkflow } from '../data/workflowApi';
import { ActiveStrip } from './ActiveStrip';
import { ActiveWorkflowGraph } from './ActiveWorkflowGraph';
import { DraftEditor } from './DraftEditor';
import { StepPanel } from './StepPanel';
import { VersionDetail } from './VersionDetail';
import { VersionList } from './VersionList';
import { YamlUpload } from './YamlUpload';
import { byName, effectiveReasoner } from './workflowModel';

// The Escalate node has no entry in the step catalogue — it isn't a step —
// so the panel gets a minimal stand-in for it instead.
const ESCALATE_STEP = {
  name: 'escalate',
  label: 'Escalate',
  description: 'Ends the run with a reason code',
  decided_by: 'code',
  removable: false,
  required_because: null,
  can_escalate: false,
  needs: [],
  produces: [],
  must_follow: [],
};

function Card({ title, children }) {
  return (
    <div className="rounded-2xl px-4 py-3" style={{ background: 'var(--bg-card-solid)', border: '1px solid var(--border)', boxShadow: 'var(--card-shadow)' }}>
      {title && (
        <h3 className="text-[11px] font-bold uppercase tracking-wide mb-2" style={{ color: 'var(--text-muted)' }}>
          {title}
        </h3>
      )}
      {children}
    </div>
  );
}

const firstDraft = (history) => history.find((v) => v.status === 'draft')?.number;

export function WorkflowView({ callerKey }) {
  const [load, setLoad] = useState({ state: 'loading' });
  const [history, setHistory] = useState([]);
  const [selected, setSelected] = useState(null);
  const [generation, setGeneration] = useState(0);
  const [mode, setMode] = useState({ kind: 'view' });
  // Its own id per opened editor, bumped on every New draft or Redraft —
  // never on a reload. Keying DraftEditor on this (not on basedOn or
  // generation) means a Redraft always remounts it with the fresh config,
  // even onto the same base version, and a sidebar action's reload never
  // remounts — and so never discards — an editor already open.
  const [editorId, setEditorId] = useState(0);
  const [panel, setPanel] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [graph, setGraph] = useState({ state: 'loading' });

  const reload = useCallback(async (select) => {
    try {
      const [overview, versions] = await Promise.all([fetchWorkflow(), fetchVersions()]);
      setLoad({ state: 'ready', overview });
      setHistory(versions);
      setSelected((cur) => select ?? cur ?? firstDraft(versions) ?? overview.active.number);
      setGeneration((g) => g + 1);
    } catch (e) {
      setLoad({ state: 'error', error: e.message });
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload, callerKey]);

  // The diagram loads on its own timeline, separate from the rest of the
  // tab: a failure here shows its own retry without blocking versions,
  // drafting or anything else. Re-fetched whenever the active version moves.
  const activeNumber = load.state === 'ready' ? load.overview.active.number : null;
  // The active version can move on (an approval elsewhere) while a graph
  // fetch for the previous one is still in flight; nothing guarantees that
  // fetch resolves before the new one's. This ref holds the version most
  // recently requested — a response is applied only when it's still the
  // latest ask, so a slow, superseded response can never clobber a newer
  // one that already landed.
  const requestedGraphVersion = useRef(null);
  const loadGraph = useCallback(async (version) => {
    requestedGraphVersion.current = version;
    setGraph({ state: 'loading' });
    try {
      const g = await fetchGraph(version);
      if (requestedGraphVersion.current !== version) return;
      setGraph({ state: 'ready', graph: g });
    } catch (e) {
      if (requestedGraphVersion.current !== version) return;
      setGraph({ state: 'error', error: e.message });
    }
  }, []);

  useEffect(() => {
    if (activeNumber != null) loadGraph(activeNumber);
  }, [activeNumber, loadGraph]);

  if (load.state === 'loading') {
    return <p className="text-[12px]" style={{ color: 'var(--text-muted)' }}>Loading the workflow…</p>;
  }
  if (load.state === 'error') {
    return (
      <div className="flex items-center gap-3 text-[12px]" style={{ color: 'var(--clr-red)' }}>
        {load.error}
        <button
          type="button"
          onClick={() => {
            setLoad({ state: 'loading' });
            reload();
          }}
          className="px-3 py-1 rounded-full"
          style={{ border: '1px solid var(--border)' }}
        >
          Retry
        </button>
      </div>
    );
  }

  const { overview } = load;
  const known = byName(overview.steps);
  const reasoner = effectiveReasoner(overview.active.config, overview.overrides);
  const isPc = overview.caller.roles.includes('PC');
  const editing = mode.kind === 'edit';

  const openEditor = (initial) => {
    setEditorId((id) => id + 1);
    setMode({ kind: 'edit', initial });
  };

  return (
    <div className="flex flex-col gap-4">
      <ActiveStrip
        overview={overview}
        canDraft={isPc && !editing}
        onNewDraft={() =>
          openEditor({ config: overview.active.config, basedOn: overview.active.number, conflicts: [] })
        }
        onUpload={() => setUploading(true)}
        onShowDrafts={() => setSelected(firstDraft(history) ?? selected)}
      />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0">
          {editing ? (
            <Card>
              <DraftEditor
                key={editorId}
                initial={mode.initial}
                catalogue={overview.steps}
                schema={overview.settings_schema}
                overrides={overview.overrides}
                activeNumber={overview.active.number}
                onCancel={() => setMode({ kind: 'view' })}
                onSaved={(v) => {
                  setMode({ kind: 'view' });
                  reload(v.number);
                }}
              />
            </Card>
          ) : (
            <Card title={`Active workflow · v${overview.active.number}`}>
              <ActiveWorkflowGraph
                config={overview.active.config}
                catalogue={overview.steps}
                reasoner={reasoner}
                graphState={graph}
                onRetryGraph={() => loadGraph(overview.active.number)}
                onSelect={setPanel}
              />
            </Card>
          )}
        </div>
        <aside className="flex flex-col gap-3 min-w-0">
          <Card title="Versions">
            <VersionList versions={history} selected={selected} onSelect={setSelected} />
          </Card>
          {selected != null && (
            <Card>
              <VersionDetail
                key={`${selected}-${generation}`}
                number={selected}
                caller={overview.caller}
                onChanged={() => reload(selected)}
                onRedraft={openEditor}
              />
            </Card>
          )}
        </aside>
      </div>
      {panel && (
        <StepPanel
          step={known[panel] || ESCALATE_STEP}
          config={overview.active.config}
          schema={overview.settings_schema}
          reasoner={reasoner}
          graph={graph.state === 'ready' ? graph.graph : undefined}
          onClose={() => setPanel(null)}
        />
      )}
      {uploading && (
        <YamlUpload
          onClose={() => setUploading(false)}
          onUploaded={(v) => {
            setUploading(false);
            reload(v.number);
          }}
        />
      )}
    </div>
  );
}
