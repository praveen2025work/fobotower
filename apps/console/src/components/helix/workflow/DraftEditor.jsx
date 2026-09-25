import { useEffect, useState } from 'react';
import { saveDraft, validateWorkflow } from '../data/workflowApi';
import { ErrorList } from './ErrorList';
import { SettingsForm } from './SettingsForm';
import { StepPanel } from './StepPanel';
import { WorkflowGraph } from './WorkflowGraph';
import { addStep, byName, effectiveReasoner, excludedSteps, setSetting } from './workflowModel';

const RETRY_MS = 3000;

function useServerCheck(config, debounceMs) {
  const [check, setCheck] = useState({ state: 'checking', errors: [] });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let live = true;
    let retry;
    const timer = setTimeout(() => {
      validateWorkflow(config)
        .then((r) => live && setCheck({ state: r.ok ? 'ok' : 'invalid', errors: r.errors }))
        .catch(() => {
          if (!live) return;
          // Keep the last answer; never turn Save on without one.
          setCheck((prev) => ({ ...prev, state: 'offline' }));
          retry = setTimeout(() => setAttempt((a) => a + 1), RETRY_MS);
        });
    }, debounceMs);
    return () => {
      live = false;
      clearTimeout(timer);
      clearTimeout(retry);
    };
  }, [config, attempt, debounceMs]);
  return [check, () => setCheck((prev) => ({ ...prev, state: 'checking' }))];
}

function CheckStatus({ check }) {
  if (check.state === 'checking') {
    return (
      <p className="text-[12px]" style={{ color: 'var(--text-muted)' }}>
        Checking…
      </p>
    );
  }
  if (check.state === 'ok') {
    return (
      <p className="text-[12px]" style={{ color: 'var(--clr-green)' }}>
        Valid. Once saved, a second Product Control user can approve it.
      </p>
    );
  }
  return (
    <div
      className="text-[12px]"
      style={{ color: check.state === 'offline' ? 'var(--clr-amber)' : 'var(--clr-red)' }}
    >
      {check.state === 'offline' && <p>Couldn't check — retrying.</p>}
      {check.errors.length > 0 && (
        <ul className="list-disc pl-4">
          {check.errors.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function DraftEditor({
  initial,
  catalogue,
  schema,
  overrides,
  activeNumber,
  onSaved,
  onCancel,
  debounceMs = 400,
}) {
  const [config, setConfig] = useState(initial.config);
  const [note, setNote] = useState('');
  const [save, setSave] = useState({ busy: false, error: null });
  const [open, setOpen] = useState(null);
  const [check, markChecking] = useServerCheck(config, debounceMs);

  const change = (next) => {
    setConfig(next);
    markChecking();
  };
  const canSave = check.state === 'ok' && note.trim().length > 0 && !save.busy;
  const submit = async () => {
    setSave({ busy: true, error: null });
    try {
      onSaved(await saveDraft({ config, note: note.trim(), basedOn: initial.basedOn }));
    } catch (e) {
      setSave({ busy: false, error: e });
    }
  };
  const reasoner = effectiveReasoner(config, overrides);
  const known = byName(catalogue);
  // A reload elsewhere (another reviewer's approve/reject/withdraw) keeps
  // this editor mounted rather than discarding it — but the version it is
  // based on can now be behind. Say so; Save still submits against the
  // base this draft was opened with.
  const staleActive = typeof activeNumber === 'number' && activeNumber !== initial.basedOn;

  return (
    <section aria-label="Draft editor" className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <h3 className="text-[14px] font-bold" style={{ color: 'var(--text-primary)' }}>
          New draft, based on v{initial.basedOn}
        </h3>
        <button
          type="button"
          onClick={onCancel}
          className="ml-auto text-[12px] px-3 py-1 rounded-full"
          style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
        >
          Cancel
        </button>
      </div>
      {staleActive && (
        <div
          role="status"
          className="rounded-lg px-3 py-2 text-[12px]"
          style={{ background: 'var(--clr-amber-bg)', color: 'var(--clr-amber)' }}
        >
          v{activeNumber} went live while you were editing. This draft is based on v{initial.basedOn}{' '}
          and will need a redraft after saving.
        </div>
      )}
      {initial.conflicts?.length > 0 && (
        <div
          role="status"
          className="rounded-lg px-3 py-2 text-[12px]"
          style={{ background: 'var(--clr-amber-bg)', color: 'var(--clr-amber)' }}
        >
          Both this draft and the active version changed {initial.conflicts.join(', ')}. The
          draft's values are kept; check them before saving.
        </div>
      )}
      <WorkflowGraph
        config={config}
        catalogue={catalogue}
        reasoner={reasoner}
        errors={check.errors}
        editing
        onSelect={setOpen}
        onChange={change}
      />
      {excludedSteps(config, catalogue).map((s) => (
        <div
          key={s.name}
          className="text-[12px] flex items-center gap-2"
          style={{ color: 'var(--text-secondary)' }}
        >
          Not in this workflow: {s.label}
          <button
            type="button"
            aria-label={`Add ${s.name}`}
            onClick={() => change(addStep(config, s.name, catalogue))}
            className="px-2 py-0.5 rounded"
            style={{ border: '1px solid var(--border)' }}
          >
            Add
          </button>
        </div>
      ))}
      <SettingsForm
        config={config}
        schema={schema}
        onChange={(s, k, v) => change(setSetting(config, s, k, v))}
      />
      <CheckStatus check={check} />
      <label
        className="text-[12px] font-semibold flex flex-col gap-1"
        style={{ color: 'var(--text-primary)' }}
      >
        Change note
        <textarea
          maxLength={500}
          rows={2}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          className="text-[12px] rounded-lg px-2 py-1.5 font-normal"
          style={{
            background: 'var(--bg-muted)',
            border: '1px solid var(--border)',
            color: 'var(--text-primary)',
          }}
          placeholder="Why is the workflow changing?"
        />
      </label>
      <ErrorList error={save.error} />
      <div>
        <button
          type="button"
          disabled={!canSave}
          onClick={submit}
          className="text-[12px] font-semibold px-4 py-1.5 rounded-full disabled:opacity-40"
          style={{ background: 'var(--clr-blue)', color: 'var(--text-on-brand)' }}
        >
          {save.busy ? 'Saving…' : 'Save draft'}
        </button>
      </div>
      {open && (
        <StepPanel
          step={known[open]}
          config={config}
          schema={schema}
          reasoner={reasoner}
          onClose={() => setOpen(null)}
        />
      )}
    </section>
  );
}
