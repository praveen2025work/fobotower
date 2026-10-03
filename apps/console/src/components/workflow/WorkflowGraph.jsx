import { ArrowRight, CirclePause } from 'lucide-react';
import { StepCard } from './StepCard';
import { byName, errorsFor, moveStep, removeStep, togglePause } from './workflowModel';

const unknownStep = (name) => ({
  name,
  unknown: true,
  label: name,
  description: 'Not a known step',
  decided_by: 'code',
  removable: true,
  required_because: null,
  can_escalate: false,
  needs: [],
  produces: [],
  must_follow: [],
});

function Gap({ name, first, paused, editing, onToggle }) {
  const marker = (
    <span
      className="flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded"
      style={{ background: 'var(--clr-amber-bg)', color: 'var(--clr-amber)' }}
    >
      <CirclePause size={10} /> Pause
    </span>
  );
  return (
    <div className="flex md:flex-col items-center justify-center gap-1 px-1 py-1 md:py-0">
      {!first && (
        <ArrowRight
          size={14}
          className="rotate-90 md:rotate-0"
          style={{ color: 'var(--text-muted)' }}
        />
      )}
      {editing ? (
        <button
          type="button"
          aria-label={`${paused ? 'Remove pause' : 'Pause'} before ${name}`}
          aria-pressed={paused}
          onClick={onToggle}
          className="rounded px-1 py-0.5 text-[10px]"
          style={{ border: '1px dashed var(--border)', color: 'var(--text-muted)' }}
        >
          {paused ? marker : '+ pause'}
        </button>
      ) : (
        paused && <span aria-label={`Pauses before ${name}`}>{marker}</span>
      )}
    </div>
  );
}

function EscalateCard({ sources }) {
  return (
    <div
      data-testid="escalate"
      className="rounded-xl px-3 py-2.5 w-full md:w-[150px] text-[11px]"
      style={{ border: '1px dashed var(--clr-red)', color: 'var(--clr-red)' }}
    >
      <div className="font-semibold">Escalate → end</div>
      <div style={{ color: 'var(--text-muted)' }}>from {sources.join(', ') || 'no step'}</div>
    </div>
  );
}

export function WorkflowGraph({
  config,
  catalogue,
  reasoner,
  errors = [],
  editing = false,
  onSelect,
  onChange,
}) {
  const known = byName(catalogue);
  const stepOf = (name) => known[name] || unknownStep(name);
  const escalating = config.steps.filter((n) => stepOf(n).can_escalate).map((n) => stepOf(n).label);
  return (
    <ol
      aria-label="Workflow steps"
      className="flex flex-col md:flex-row md:flex-wrap md:items-center gap-1"
    >
      {config.steps.map((name, i) => (
        <li key={name} className="flex flex-col md:flex-row md:items-center">
          <Gap
            name={name}
            first={i === 0}
            paused={config.pause_before.includes(name)}
            editing={editing}
            onToggle={() => onChange(togglePause(config, name))}
          />
          <StepCard
            step={stepOf(name)}
            index={i}
            total={config.steps.length}
            reasoner={reasoner}
            errors={errorsFor(errors, name)}
            editing={editing}
            onSelect={onSelect}
            onMove={(index, delta) => onChange(moveStep(config, index, delta))}
            onRemove={(n) => onChange(removeStep(config, n))}
          />
        </li>
      ))}
      <li className="md:ml-2 mt-2 md:mt-0">
        <EscalateCard sources={escalating} />
      </li>
    </ol>
  );
}
