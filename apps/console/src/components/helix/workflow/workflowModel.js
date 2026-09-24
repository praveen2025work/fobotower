/** Pure helpers for the Workflow tab. Nothing here changes its inputs. */

export const TAG_STYLE = {
  grey: { bg: 'var(--bg-muted)', fg: 'var(--text-secondary)' },
  green: { bg: 'var(--clr-green-bg)', fg: 'var(--clr-green)' },
  purple: { bg: 'var(--clr-purple-bg)', fg: 'var(--clr-purple)' },
  blue: { bg: 'var(--clr-blue-bg)', fg: 'var(--clr-blue)' },
  amber: { bg: 'var(--clr-amber-bg)', fg: 'var(--clr-amber)' },
  red: { bg: 'var(--clr-red-bg)', fg: 'var(--clr-red)' },
};

export const STATUS_TONE = { active: 'green', draft: 'amber', superseded: 'grey', rejected: 'red' };

/** The chips that say who decides a step, from the registry's decided_by. */
export function decidedByChips(decidedBy, reasoner) {
  switch (decidedBy) {
    case 'playbook+reasoner':
      return [
        { label: 'Playbook', tone: 'green' },
        { label: `Reasoner: ${reasoner}`, tone: 'purple' },
      ];
    case 'code+model':
      return [
        { label: 'Code', tone: 'grey' },
        { label: 'Multi-cause: model (not built)', tone: 'grey' },
      ];
    case 'template':
      return [{ label: 'Template · model planned', tone: 'grey' }];
    case 'human':
      return [{ label: 'Human', tone: 'blue' }];
    default:
      return [{ label: 'Code', tone: 'grey' }];
  }
}

/** The reasoner actually in force: an environment override beats the config. */
export const effectiveReasoner = (config, overrides) =>
  overrides?.reasoner || config.settings.reason.reasoner;

export const byName = (catalogue) => Object.fromEntries(catalogue.map((s) => [s.name, s]));

/** The step an error message is about: the first quoted token after the
 *  leading "<field>: " prefix, e.g. "validate" in
 *  "steps: 'validate' needs 'draft' before it runs — produced by draft", or
 *  after "<field>: must include '<step>'" for a missing required pause. */
const subjectOf = (e) => /^[a-z_.]+: (?:must include )?'([^']+)'/.exec(e)?.[1];

/** Errors whose subject is this step — not just messages that quote its name
 *  in passing (a message can quote a data key that is also a step name). */
export const errorsFor = (errors, name) => errors.filter((e) => subjectOf(e) === name);

export function moveStep(config, index, delta) {
  const to = index + delta;
  if (to < 0 || to >= config.steps.length) return config;
  const steps = [...config.steps];
  [steps[index], steps[to]] = [steps[to], steps[index]];
  return { ...config, steps };
}

export const removeStep = (config, name) => ({
  ...config,
  steps: config.steps.filter((s) => s !== name),
  pause_before: config.pause_before.filter((s) => s !== name),
});

/** Put a step back where the registry places it among the steps present. */
export function addStep(config, name, catalogue) {
  const order = catalogue.map((s) => s.name);
  const at = config.steps.findIndex((s) => order.indexOf(s) > order.indexOf(name));
  const steps =
    at === -1
      ? [...config.steps, name]
      : [...config.steps.slice(0, at), name, ...config.steps.slice(at)];
  return { ...config, steps };
}

export const togglePause = (config, name) => ({
  ...config,
  pause_before: config.pause_before.includes(name)
    ? config.pause_before.filter((s) => s !== name)
    : [...config.pause_before, name],
});

export const setSetting = (config, section, key, value) => ({
  ...config,
  settings: { ...config.settings, [section]: { ...config.settings[section], [key]: value } },
});

export const excludedSteps = (config, catalogue) =>
  catalogue.filter((s) => s.removable && !config.steps.includes(s.name));

/** Settings sections shown with each step; the session service serves the reasoner. */
export const SETTINGS_FOR_STEP = {
  gather: ['gather'],
  reason: ['reason', 'session_service'],
  validate: ['validate'],
  review: ['review'],
};

export const humanize = (key) => key.replace(/_/g, ' ');

export const showValue = (v) => {
  if (Array.isArray(v)) return v.length ? v.join(', ') : '(none)';
  if (v === null || v === undefined || v === '') return '(unset)';
  return String(v);
};

const stepNo = (i) => `step ${i + 1}`;

/** One diff entry from the API, as a line a controller can read. */
export function describeChange({ path, kind, before, after }) {
  const [head, ...rest] = path.split('.');
  const name = rest.join('.');
  if (head === 'steps') {
    if (kind === 'removed') return `${name} removed (was ${stepNo(before)})`;
    if (kind === 'added') return `${name} added as ${stepNo(after)}`;
    return `${name} moved from ${stepNo(before)} to ${stepNo(after)}`;
  }
  if (head === 'pause_before') {
    return `pause ${kind === 'added' ? 'added' : 'removed'} before ${name}`;
  }
  const label = head === 'settings' ? name : path;
  return `${label}: ${showValue(before)} → ${showValue(after)}`;
}

export const when = (iso) =>
  iso
    ? new Date(iso).toLocaleString('en-GB', {
        day: '2-digit',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit',
        timeZone: 'UTC',
      })
    : '';
