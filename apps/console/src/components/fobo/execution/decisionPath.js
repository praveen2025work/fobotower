/**
 * A break's path through the playbook, as a sequence of steps.
 *
 * Built from the finding the `reason` node recorded, so it shows what the
 * orchestrator actually did: which rule fired, the category and side it
 * implied, the verdict the playbook prescribes, which guard changed it.
 */
export function decisionPath(f) {
  if (!f) return [];
  const steps = [];

  if (f.deterministic) {
    const rule = f.rule_applied ?? f.pattern;
    steps.push({ kind: 'rule', text: rule ? `${rule} fired` : 'Rule applied', title: f.root_cause });
  } else {
    steps.push({
      kind: 'judgement',
      text: 'Needs judgement',
      title: f.unresolved_reason ?? 'No single rule settles this break',
    });
  }

  steps.push({
    kind: 'category',
    text: `${f.category_code} · ${f.category_name}`,
    title: 'Break category (playbook §9)',
  });

  if (f.side) {
    steps.push({ kind: 'side', text: `${f.side} side`, title: 'Where the cause originates' });
  } else if (!f.deterministic) {
    steps.push({ kind: 'side', text: 'side unknown', title: 'The evidence does not say which side is wrong' });
  }

  if (f.deterministic) {
    steps.push({
      kind: 'playbook',
      text: `Playbook: ${label(f.verdict_proposed) ?? '—'}`,
      title: 'Default verdict for this category and side',
    });
  } else {
    steps.push({
      kind: 'reasoner',
      text: `Reasoner: ${f.reasoner ?? 'none'}`,
      title: f.reasoner === 'none' ? 'No reasoner configured — no LLM called' : 'Sent for judgement',
    });
  }

  for (const reason of f.guard_reasons ?? []) {
    const code = /^([A-Z]\d+|§\d+)/.exec(reason)?.[1] ?? 'guard';
    steps.push({ kind: 'guard', text: `${code} guard`, title: reason });
  }

  steps.push({ kind: 'verdict', verdict: f.verdict, text: label(f.verdict) ?? '—' });
  return steps;
}

const LABELS = {
  POST: 'POST',
  DO_NOT_POST: 'DO NOT POST',
  ESCALATE: 'ESCALATE',
  CORRECT_AND_REPOST: 'CORRECT & RE-POST',
};

export function label(verdict) {
  return verdict ? LABELS[verdict] ?? verdict : null;
}
