import { mono } from '../lib/format';

function Step({ n, title, children }) {
  return (
    <div className="mb-3">
      <div
        className="text-[11.5px] font-semibold flex items-baseline gap-1.5"
        style={{ color: 'var(--text-primary)' }}
      >
        <span
          className="shrink-0 w-4 h-4 rounded-full inline-flex items-center justify-center text-[10px]"
          style={{ background: 'var(--bg-muted)', color: 'var(--text-secondary)' }}
        >
          {n}
        </span>
        {title}
      </div>
      <div className="mt-1 pl-[22px] flex flex-col gap-1">{children}</div>
    </div>
  );
}

const th = { color: 'var(--text-muted)', fontWeight: 600 };
const td = { color: 'var(--text-secondary)' };

/** Read the entire "Apply playbook" step: how a break is settled, from named
 *  patterns down through the reasoner and the hard guards. Every value comes
 *  from `graph.decision` (Task A's GET /api/workflow/graph); nothing here is
 *  typed in. */
export function DecisionTree({ decision, reasoner }) {
  const reasonerLine =
    reasoner === 'none' ? 'a person — logged as Novel break' : reasoner;
  return (
    <div className="text-[11.5px]">
      <Step n={1} title="Named patterns, tried in order:">
        <ol className="flex flex-col gap-0.5">
          {decision.patterns.map((p) => (
            <li key={p.code} data-testid="decision-pattern">
              <span style={mono} className="font-semibold">
                {p.code}
              </span>{' '}
              — {p.meaning}
            </li>
          ))}
        </ol>
      </Step>

      <Step n={2} title="Single cause:">
        <p style={{ color: 'var(--text-secondary)' }}>
          Exactly one cause check fired — its category and side settle the verdict.
        </p>
        <table className="w-full text-left" style={{ borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th className="pr-2 py-0.5 font-semibold" style={th}>
                Check
              </th>
              <th className="pr-2 py-0.5 font-semibold" style={th}>
                Category
              </th>
              <th className="py-0.5 font-semibold" style={th}>
                Side
              </th>
            </tr>
          </thead>
          <tbody>
            {decision.cause_checks.map((c) => (
              <tr key={c.check}>
                <td className="pr-2 py-0.5" style={{ ...mono, ...td }}>
                  {c.check}
                </td>
                <td className="pr-2 py-0.5" style={td}>
                  {c.category_name}
                </td>
                <td className="py-0.5" style={td}>
                  {c.side}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Step>

      <Step n={3} title="Verdict from the playbook:">
        <table className="w-full text-left" style={{ borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th className="pr-2 py-0.5 font-semibold" style={th}>
                Category
              </th>
              <th className="pr-2 py-0.5 font-semibold" style={th}>
                FO
              </th>
              <th className="py-0.5 font-semibold" style={th}>
                BO
              </th>
            </tr>
          </thead>
          <tbody>
            {decision.default_verdicts.map((v) => (
              <tr key={v.category} data-testid={`verdict-row-${v.category}`}>
                <td className="pr-2 py-0.5" style={td}>
                  {v.category_name}
                </td>
                <td className="pr-2 py-0.5" style={{ ...mono, ...td }}>
                  {v.FO}
                </td>
                <td className="py-0.5" style={{ ...mono, ...td }}>
                  {v.BO}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Step>

      <Step n={4} title="No pattern or cause:">
        <p style={{ color: 'var(--text-secondary)' }}>
          Goes to the reasoner in force: {reasonerLine}.
        </p>
      </Step>

      <Step n={5} title="Every verdict then passes the guards:">
        <ul className="flex flex-col gap-0.5">
          {decision.guards.map((g) => (
            <li key={g.id}>
              <span data-testid={`guard-${g.id}`} style={mono} className="font-semibold">
                {g.id}
              </span>{' '}
              <span style={{ color: 'var(--text-secondary)' }}>— {g.rule}</span>
            </li>
          ))}
        </ul>
      </Step>

      <ul className="flex flex-col gap-0.5 mt-1">
        {decision.defined_in.map((path) => (
          <li key={path} className="text-[10.5px]" style={{ ...mono, color: 'var(--text-muted)' }}>
            {path}
          </li>
        ))}
      </ul>
    </div>
  );
}
