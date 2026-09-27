import { describe, expect, it } from 'vitest';
import fixture from './__fixtures__/workflow.json';
import {
  addStep,
  decidedByChips,
  describeChange,
  effectiveReasoner,
  errorsFor,
  excludedSteps,
  moveStep,
  removeStep,
  setSetting,
  togglePause,
} from './workflowModel';

const config = () => structuredClone(fixture.active.config);

describe('workflowModel', () => {
  it('tags the playbook step with the reasoner in force', () => {
    expect(decidedByChips('playbook+reasoner', 'none')).toEqual([
      { label: 'Playbook', tone: 'green' },
      { label: 'Reasoner: none', tone: 'purple' },
    ]);
    expect(decidedByChips('human')).toEqual([{ label: 'Human', tone: 'blue' }]);
    expect(decidedByChips('code')).toEqual([{ label: 'Code', tone: 'grey' }]);
    expect(decidedByChips('code+model')).toEqual([
      { label: 'Code', tone: 'grey' },
      { label: 'Multi-cause: model (not built)', tone: 'grey' },
    ]);
    expect(decidedByChips('template')).toEqual([
      { label: 'Template · model planned', tone: 'grey' },
    ]);
  });

  it('prefers an environment override to the configured reasoner', () => {
    expect(effectiveReasoner(config(), {})).toBe('none');
    expect(effectiveReasoner(config(), { reasoner: 'direct' })).toBe('direct');
  });

  it('moves a step without touching the original', () => {
    const before = config();
    const after = moveStep(before, 4, 1);
    expect(after.steps.slice(4, 6)).toEqual(['draft', 'rank']);
    expect(before.steps[4]).toBe('rank');
    expect(moveStep(before, 0, -1)).toBe(before);
  });

  it('removing a step also removes its pause', () => {
    const paused = togglePause(config(), 'rank');
    expect(removeStep(paused, 'rank').pause_before).toEqual(['review']);
  });

  it('adds a step back where the registry puts it', () => {
    const without = removeStep(config(), 'rank');
    expect(addStep(without, 'rank', fixture.steps).steps).toEqual(config().steps);
    expect(excludedSteps(without, fixture.steps).map((s) => s.name)).toEqual(['rank']);
  });

  it('sets a setting immutably', () => {
    const before = config();
    const after = setSetting(before, 'gather', 'priors_lookback_days', 90);
    expect(after.settings.gather.priors_lookback_days).toBe(90);
    expect(before.settings.gather.priors_lookback_days).toBe(180);
  });

  it('finds the errors that name a step', () => {
    const errors = ["steps: 'draft' needs 'pattern_groups' before it runs", 'other'];
    expect(errorsFor(errors, 'draft')).toEqual([errors[0]]);
  });

  it('attributes an error to its subject, not any step it happens to quote', () => {
    const errors = ["steps: 'validate' needs 'draft' before it runs — produced by draft"];
    expect(errorsFor(errors, 'draft')).toEqual([]);
    expect(errorsFor(errors, 'validate')).toEqual(errors);
  });

  it('attributes a missing required pause to the step it guards', () => {
    const errors = ["pause_before: must include 'review' — no decision is recorded without a person"];
    expect(errorsFor(errors, 'review')).toEqual(errors);
  });

  it('attaches a settings error to no step', () => {
    const errors = ['settings.gather.prior_lookback_days: Extra inputs are not permitted'];
    expect(errorsFor(errors, 'gather')).toEqual([]);
  });

  it('reads each kind of change as a sentence', () => {
    expect(describeChange({ path: 'steps.rank', kind: 'removed', before: 4 })).toBe(
      'rank removed (was step 5)',
    );
    expect(describeChange({ path: 'steps.rank', kind: 'added', after: 4 })).toBe(
      'rank added as step 5',
    );
    expect(describeChange({ path: 'steps.rank', kind: 'moved', before: 4, after: 6 })).toBe(
      'rank moved from step 5 to step 7',
    );
    expect(describeChange({ path: 'pause_before.reason', kind: 'added' })).toBe(
      'pause added before reason',
    );
    expect(
      describeChange({
        path: 'settings.gather.priors_lookback_days',
        kind: 'changed',
        before: 180,
        after: 90,
      }),
    ).toBe('gather.priors_lookback_days: 180 → 90');
  });
});
