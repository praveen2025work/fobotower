import { describe, expect, it } from 'vitest';
import { diffLines, stripHeader, tokenizeYamlLine } from './yamlText';

describe('tokenizeYamlLine', () => {
  it('reads a full comment line as one comment token', () => {
    expect(tokenizeYamlLine('# FOBO investigation workflow, version 1 (active)')).toEqual([
      { text: '# FOBO investigation workflow, version 1 (active)', kind: 'comment' },
    ]);
  });

  it('tokenizes an indented key with a number value', () => {
    expect(tokenizeYamlLine('  priors_lookback_days: 180')).toEqual([
      { text: '  ', kind: 'text' },
      { text: 'priors_lookback_days', kind: 'key' },
      { text: ':', kind: 'punct' },
      { text: ' ', kind: 'text' },
      { text: '180', kind: 'number' },
    ]);
  });

  it('does not treat an arbitrary word as a bool — only true/false/null are', () => {
    expect(tokenizeYamlLine('  reasoner: none')).toEqual([
      { text: '  ', kind: 'text' },
      { text: 'reasoner', kind: 'key' },
      { text: ':', kind: 'punct' },
      { text: ' ', kind: 'text' },
      { text: 'none', kind: 'text' },
    ]);
  });

  it('tokenizes a quoted string value', () => {
    expect(tokenizeYamlLine("version: '1.0'")).toEqual([
      { text: 'version', kind: 'key' },
      { text: ':', kind: 'punct' },
      { text: ' ', kind: 'text' },
      { text: "'1.0'", kind: 'string' },
    ]);
  });

  it('tokenizes a list item as a punct dash plus its scalar', () => {
    expect(tokenizeYamlLine('- resolve')).toEqual([
      { text: '-', kind: 'punct' },
      { text: ' ', kind: 'text' },
      { text: 'resolve', kind: 'text' },
    ]);
  });

  it('tokenizes a key line with no value', () => {
    expect(tokenizeYamlLine('pause_before:')).toEqual([
      { text: 'pause_before', kind: 'key' },
      { text: ':', kind: 'punct' },
    ]);
  });

  it('recognizes true/false/null as bool', () => {
    expect(tokenizeYamlLine('  enabled: true')).toEqual([
      { text: '  ', kind: 'text' },
      { text: 'enabled', kind: 'key' },
      { text: ':', kind: 'punct' },
      { text: ' ', kind: 'text' },
      { text: 'true', kind: 'bool' },
    ]);
    expect(tokenizeYamlLine('  reasoner: null')).toEqual([
      { text: '  ', kind: 'text' },
      { text: 'reasoner', kind: 'key' },
      { text: ':', kind: 'punct' },
      { text: ' ', kind: 'text' },
      { text: 'null', kind: 'bool' },
    ]);
  });

  it('reproduces the original line when every token is concatenated', () => {
    for (const line of [
      '# a comment',
      '  priors_lookback_days: 180',
      '  reasoner: none',
      "version: '1.0'",
      '- resolve',
      'pause_before:',
      '    - materiality_threshold',
      '',
    ]) {
      const joined = tokenizeYamlLine(line)
        .map((t) => t.text)
        .join('');
      expect(joined).toBe(line);
    }
  });
});

describe('stripHeader', () => {
  const HEADER = [
    '# FOBO investigation workflow, version 1 (active)',
    '# Drafted by system; approved by system.',
    '# Note: seeded from config/workflow/fobo-investigation.yaml',
    '#',
    '# Upload this file in the Workflow tab to propose it as a draft; a second',
    '# Product Control user must approve it before new runs use it.',
  ].join('\n');
  const BODY = "version: '1.0'\nname: fobo-investigation\nsteps:\n- resolve\n";

  it('drops the leading comment block (as actually returned by the API, with no blank line after it)', () => {
    expect(stripHeader(`${HEADER}\n${BODY}`)).toBe(BODY);
  });

  it('also drops a single blank line after the header, if present', () => {
    expect(stripHeader(`${HEADER}\n\n${BODY}`)).toBe(BODY);
  });

  it('leaves the body untouched when there is no header', () => {
    expect(stripHeader(BODY)).toBe(BODY);
  });

  it('does not mutate anything beyond the header', () => {
    const input = `${HEADER}\n${BODY}`;
    const before = input;
    stripHeader(input);
    expect(input).toBe(before);
  });
});

describe('diffLines', () => {
  it('yields one del and one add for a one-line change, keeping the rest same and in order', () => {
    const a = 'a\nb\nc';
    const b = 'a\nx\nc';
    expect(diffLines(a, b)).toEqual([
      { kind: 'same', line: 'a' },
      { kind: 'del', line: 'b' },
      { kind: 'add', line: 'x' },
      { kind: 'same', line: 'c' },
    ]);
  });

  it('handles empty inputs', () => {
    expect(diffLines('', '')).toEqual([]);
    expect(diffLines('', 'a')).toEqual([{ kind: 'add', line: 'a' }]);
    expect(diffLines('a', '')).toEqual([{ kind: 'del', line: 'a' }]);
  });

  it('does not mutate its inputs', () => {
    const a = 'a\nb';
    const b = 'a\nc';
    diffLines(a, b);
    expect(a).toBe('a\nb');
    expect(b).toBe('a\nc');
  });

  it('preserves order across an addition and a removal at different points', () => {
    const a = 'a\nb\nc\nd';
    const b = 'a\nc\nd\ne';
    expect(diffLines(a, b)).toEqual([
      { kind: 'same', line: 'a' },
      { kind: 'del', line: 'b' },
      { kind: 'same', line: 'c' },
      { kind: 'same', line: 'd' },
      { kind: 'add', line: 'e' },
    ]);
  });
});
