import { mono } from '../lib/format';
import { Drawer } from '../ui/Drawer';
import { Chip } from './StepCard';
import { DecisionTree } from './DecisionTree';
import { SETTINGS_FOR_STEP, decidedByChips, humanize, showValue } from './workflowModel';

function Section({ title, children }) {
  return (
    <section className="mb-4">
      <h4
        className="text-[11px] font-bold uppercase tracking-wide mb-1.5"
        style={{ color: 'var(--text-muted)' }}
      >
        {title}
      </h4>
      {children}
    </section>
  );
}

function Keys({ keys }) {
  if (!keys.length) return <span className="text-[12px]">(none)</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {keys.map((k) => (
        <span
          key={k}
          className="text-[10.5px] px-1.5 py-0.5 rounded"
          style={{ ...mono, background: 'var(--bg-muted)', color: 'var(--text-secondary)' }}
        >
          {k}
        </span>
      ))}
    </div>
  );
}

/** Router rule + escalation codes + where it's defined, for a step that can
 *  escalate; the Apply playbook step also gets the full decision tree. */
function HowItDecides({ step, graph, reasoner }) {
  if (!graph) return null;

  if (step.name === 'escalate') {
    const esc = graph.logic.escalate;
    return (
      <Section title="How it decides">
        <p className="text-[12px] mb-1.5" style={{ color: 'var(--text-secondary)' }}>
          Ends the run. The reason code says which step could not proceed.
        </p>
        <ul className="flex flex-col gap-1.5 mb-1.5">
          {esc.raised_by.map((group) => (
            <li key={group.step}>
              <div
                className="text-[10.5px] font-bold uppercase tracking-wide mb-0.5"
                style={{ color: 'var(--text-muted)' }}
              >
                {group.label}
              </div>
              <ul className="flex flex-col gap-0.5">
                {group.codes.map((code) => (
                  <li
                    key={code}
                    data-testid={`escalate-reason-${code}`}
                    className="text-[11px]"
                    style={mono}
                  >
                    {code}
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
        {esc.other_known.length > 0 && (
          <p
            className="text-[10.5px] mb-1.5"
            style={{ color: 'var(--text-muted)' }}
            data-testid="escalate-other-known"
          >
            Accepted by escalate() but not raised by any step in this workflow:{' '}
            <span style={mono}>{esc.other_known.join(', ')}</span>
          </p>
        )}
        <p className="text-[10.5px]" style={{ ...mono, color: 'var(--text-muted)' }}>
          {esc.defined_in}
        </p>
      </Section>
    );
  }

  const logic = graph.logic[step.name];
  if (!logic) return null;
  const canEscalate = logic.escalates_when.length > 0;

  return (
    <Section title="How it decides">
      {canEscalate && (
        <>
          <p className="text-[12px] mb-1" style={{ color: 'var(--text-secondary)' }}>
            {graph.router.rule}
          </p>
          <p className="text-[10.5px] mb-2" style={{ ...mono, color: 'var(--text-muted)' }}>
            {graph.router.defined_in}
          </p>
          <h5 className="text-[10.5px] font-bold uppercase tracking-wide mb-1" style={{ color: 'var(--text-muted)' }}>
            Escalates when
          </h5>
          <ul className="flex flex-col gap-1 mb-2">
            {logic.escalates_when.map(({ code, when }) => (
              <li key={code} data-testid={`escalates-${code}`} className="text-[11.5px]">
                <span style={mono} className="font-semibold">
                  {code}
                </span>{' '}
                — {when}
              </li>
            ))}
          </ul>
        </>
      )}
      <p
        className="text-[10.5px] mb-2"
        style={{ ...mono, color: 'var(--text-muted)' }}
        data-testid="step-defined-in"
      >
        {canEscalate ? logic.defined_in : `Defined in: ${logic.defined_in}`}
      </p>
      {step.name === 'reason' && (
        <>
          <h5 className="text-[10.5px] font-bold uppercase tracking-wide mb-1.5" style={{ color: 'var(--text-muted)' }}>
            Decision tree
          </h5>
          <DecisionTree decision={graph.decision} reasoner={reasoner} />
        </>
      )}
    </Section>
  );
}

export function StepPanel({ step, config, schema, reasoner, graph, onClose }) {
  const sections = SETTINGS_FOR_STEP[step.name] || [];
  // Escalate isn't a registered step — it has no needs/produces/settings of
  // its own (WorkflowView.jsx's ESCALATE_STEP stand-in gives it empty
  // arrays for those), so those sections would otherwise show nothing but
  // "(none)" / "This step has no settings." with nothing for a controller
  // to learn from them.
  const isEscalate = step.name === 'escalate';
  return (
    <Drawer title={step.label} subtitle={`${step.name} · ${step.description}`} width={480} onClose={onClose}>
      <HowItDecides step={step} graph={graph} reasoner={reasoner} />
      <Section title="Decided by">
        <div className="flex flex-wrap gap-1">
          {decidedByChips(step.decided_by, reasoner).map((c) => (
            <Chip key={c.label} {...c} />
          ))}
        </div>
      </Section>
      {step.required_because && (
        <Section title="Why it can't be removed">
          <p className="text-[12.5px]" style={{ color: 'var(--text-primary)' }}>
            {step.required_because}
          </p>
        </Section>
      )}
      {!isEscalate && (
        <Section title="Needs">
          <Keys keys={step.needs} />
        </Section>
      )}
      {!isEscalate && (
        <Section title="Produces">
          <Keys keys={step.produces} />
        </Section>
      )}
      {step.must_follow.length > 0 && (
        <Section title="Must come after">
          <Keys keys={step.must_follow} />
        </Section>
      )}
      {sections.map((sec) => (
        <Section key={sec} title={`Settings · ${sec}`}>
          <dl className="flex flex-col gap-2">
            {Object.entries(schema[sec] || {}).map(([key, meta]) => (
              <div key={key}>
                <dt className="text-[12px] font-semibold" style={{ color: 'var(--text-primary)' }}>
                  {humanize(key)}
                </dt>
                <dd className="text-[12px]" style={{ ...mono, color: 'var(--text-secondary)' }}>
                  {showValue(config.settings[sec]?.[key])}
                </dd>
                <dd className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                  {meta.description}
                </dd>
              </div>
            ))}
          </dl>
        </Section>
      ))}
      {!isEscalate && !sections.length && (
        <p className="text-[12px]" style={{ color: 'var(--text-muted)' }}>
          This step has no settings.
        </p>
      )}
    </Drawer>
  );
}
