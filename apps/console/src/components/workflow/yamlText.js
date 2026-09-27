/** Pure helpers for reading and diffing workflow YAML. Nothing here mutates
 *  its inputs. */

const BOOL_RE = /^(true|false|null)$/;
const NUMBER_RE = /^-?\d+(\.\d+)?$/;
const QUOTED_RE = /^(['"]).*\1$/;
// A key: the first run of non-colon, non-space characters, followed by a
// colon that ends the line or is followed by whitespace (so a value like
// "http://x" inside a plain scalar doesn't get mistaken for a key).
const KEY_RE = /^([^:\s][^:]*):(\s|$)/;

function tokenizeScalar(text) {
  if (text === '') return [];
  if (QUOTED_RE.test(text)) return [{ text, kind: 'string' }];
  if (BOOL_RE.test(text)) return [{ text, kind: 'bool' }];
  if (NUMBER_RE.test(text)) return [{ text, kind: 'number' }];
  return [{ text, kind: 'text' }];
}

/** Split off a leading run of spaces from `text`, returning [space, rest]. */
function splitLeadingSpace(text) {
  const match = /^ */.exec(text);
  return [match[0], text.slice(match[0].length)];
}

/** One line of the workflow YAML, broken into coloured tokens. Concatenating
 *  every token's `text` reproduces the original line exactly. */
export function tokenizeYamlLine(line) {
  const [indent, rest] = splitLeadingSpace(line);
  const tokens = [];
  if (indent) tokens.push({ text: indent, kind: 'text' });
  if (rest === '') return tokens;
  if (rest.startsWith('#')) {
    tokens.push({ text: rest, kind: 'comment' });
    return tokens;
  }
  if (rest === '-' || rest.startsWith('- ')) {
    tokens.push({ text: '-', kind: 'punct' });
    const [space, value] = splitLeadingSpace(rest.slice(1));
    if (space) tokens.push({ text: space, kind: 'text' });
    tokens.push(...tokenizeScalar(value));
    return tokens;
  }
  const keyMatch = KEY_RE.exec(rest);
  if (keyMatch) {
    const key = keyMatch[1];
    tokens.push({ text: key, kind: 'key' });
    tokens.push({ text: ':', kind: 'punct' });
    const [space, value] = splitLeadingSpace(rest.slice(key.length + 1));
    if (space) tokens.push({ text: space, kind: 'text' });
    tokens.push(...tokenizeScalar(value));
    return tokens;
  }
  tokens.push(...tokenizeScalar(rest));
  return tokens;
}

/** Drops the leading "# ..." header block that yaml_io.py puts atop every
 *  version's YAML (it names the version, status, drafter and approver, so it
 *  naturally differs between versions and would be pure noise in a diff),
 *  plus a single blank line after it if there is one. */
export function stripHeader(yaml) {
  const lines = yaml.split('\n');
  let i = 0;
  while (i < lines.length && lines[i].startsWith('#')) i++;
  if (lines[i] === '') i++;
  return lines.slice(i).join('\n');
}

const linesOf = (text) => (text === '' ? [] : text.split('\n'));

/** A line-level LCS diff between two YAML texts. `a` and `b` are read, never
 *  written. */
export function diffLines(a, b) {
  const left = linesOf(a);
  const right = linesOf(b);
  const n = left.length;
  const m = right.length;
  const dp = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = left[i] === right[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const result = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (left[i] === right[j]) {
      result.push({ kind: 'same', line: left[i] });
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      result.push({ kind: 'del', line: left[i] });
      i++;
    } else {
      result.push({ kind: 'add', line: right[j] });
      j++;
    }
  }
  while (i < n) {
    result.push({ kind: 'del', line: left[i] });
    i++;
  }
  while (j < m) {
    result.push({ kind: 'add', line: right[j] });
    j++;
  }
  return result;
}
