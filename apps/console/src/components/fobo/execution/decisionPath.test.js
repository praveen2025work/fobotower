import { describe, expect, it } from 'vitest';

import { decisionPath, label } from './decisionPath';

const settled = {
  deterministic: true,
  rule_applied: 'C1',
  root_cause: 'Nostro statement received after 23:30 cutoff',
  category_code: 'C',
  category_name: 'Redemption break',
  side: 'BO',
  verdict_proposed: 'POST',
  verdict: 'POST',
  guard_reasons: ['P1: depends on unset parameters — requires controller confirmation'],
};

const judgement = {
  deterministic: false,
  unresolved_reason: 'C3 identifies a difference but not which side is at fault',
  category_code: 'H',
  category_name: 'Novel break',
  side: null,
  reasoner: 'none',
  verdict_proposed: null,
  verdict: 'ESCALATE',
  guard_reasons: ['R6: root cause not evidenced — escalate, do not post'],
};

const kinds = (f) => decisionPath(f).map((s) => s.kind);

describe('decisionPath', () => {
  it('traces a settled break rule -> category -> side -> playbook -> guard -> verdict', () => {
    expect(kinds(settled)).toEqual(['rule', 'category', 'side', 'playbook', 'guard', 'verdict']);
  });

  it('names the rule that fired', () => {
    expect(decisionPath(settled)[0].text).toBe('C1 fired');
  });

  it('shows the verdict the playbook prescribed before any guard', () => {
    expect(decisionPath(settled).find((s) => s.kind === 'playbook').text).toBe('Playbook: POST');
  });

  it('routes an unsettled break through the reasoner, not the playbook', () => {
    const k = kinds(judgement);
    expect(k[0]).toBe('judgement');
    expect(k).toContain('reasoner');
    expect(k).not.toContain('playbook');
  });

  it('says the side is unknown rather than omitting it', () => {
    expect(decisionPath(judgement).find((s) => s.kind === 'side').text).toBe('side unknown');
  });

  it('labels each guard by its rule code', () => {
    expect(decisionPath(judgement).find((s) => s.kind === 'guard').text).toBe('R6 guard');
  });

  it('keeps the full guard reason for the tooltip', () => {
    expect(decisionPath(settled).find((s) => s.kind === 'guard').title).toMatch(/controller confirmation/);
  });

  it('always ends at the final verdict', () => {
    for (const f of [settled, judgement]) {
      const path = decisionPath(f);
      expect(path.at(-1).kind).toBe('verdict');
      expect(path.at(-1).verdict).toBe(f.verdict);
    }
  });

  it('shows the override when a guard changed the playbook verdict', () => {
    const overridden = { ...settled, side: 'FO', verdict: 'DO_NOT_POST',
      guard_reasons: ['R2: cause originates in Front Office — do not post'] };
    const path = decisionPath(overridden);
    expect(path.find((s) => s.kind === 'playbook').text).toBe('Playbook: POST');
    expect(path.at(-1).text).toBe('DO NOT POST');
  });

  it('returns nothing for a missing finding', () => {
    expect(decisionPath(undefined)).toEqual([]);
  });

  it('labels verdicts in controller wording', () => {
    expect(label('DO_NOT_POST')).toBe('DO NOT POST');
    expect(label('CORRECT_AND_REPOST')).toBe('CORRECT & RE-POST');
  });
});
