import { mono } from '../lib/format';
import { Drawer } from '../ui/Drawer';
import { Chip } from './StepCard';
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

export function StepPanel({ step, config, schema, reasoner, onClose }) {
  const sections = SETTINGS_FOR_STEP[step.name] || [];
  return (
    <Drawer title={step.label} subtitle={`${step.name} · ${step.description}`} width={480} onClose={onClose}>
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
      <Section title="Needs">
        <Keys keys={step.needs} />
      </Section>
      <Section title="Produces">
        <Keys keys={step.produces} />
      </Section>
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
      {!sections.length && (
        <p className="text-[12px]" style={{ color: 'var(--text-muted)' }}>
          This step has no settings.
        </p>
      )}
    </Drawer>
  );
}
