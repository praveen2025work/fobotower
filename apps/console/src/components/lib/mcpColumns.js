/**
 * Table columns for each MCP tool the orchestrator records. A column is shown
 * only when the tool actually returned that field, and a field with no spec
 * here is still shown, so the table never hides or invents data.
 */

const col = (key, label, extra = {}) => ({ key, label, ...extra });

export const TOOL_COLUMNS = {
  get_breaks: [
    col('breakId', 'Break'),
    col('masterBook', 'Master book', { mono: true }),
    col('pattern', 'Pattern', { mono: true }),
    col('line', 'Line'),
    col('delta', 'Delta', { align: 'right', mono: true }),
    col('type', 'Draft'),
    col('ageSessions', 'Age (sessions)', { align: 'right' }),
  ],
  get_break_legs: [
    col('breakId', 'Break'),
    col('masterBook', 'Master book', { mono: true }),
    col('leg', 'Leg'),
    col('amount', 'Amount', { align: 'right', mono: true }),
  ],
  kg_lineage: [
    col('breakId', 'Break'),
    col('masterBook', 'Master book', { mono: true }),
    col('path', 'Lineage (as of COB)'),
  ],
  similar_breaks: [
    col('breakId', 'Break'),
    col('masterBook', 'Master book', { mono: true }),
    col('priors', 'Priors', { align: 'right' }),
    col('approved', 'Approved', { align: 'right' }),
  ],
  grounding_check: [
    col('adjId', 'Adjustment'),
    col('figure', 'Drafted figure', { align: 'right', mono: true }),
    col('source', 'MB Rec source', { align: 'right', mono: true }),
    col('result', 'Result'),
  ],
  get_session_state: [
    col('pattern', 'Pattern', { mono: true }),
    col('label', 'Description'),
    col('pending', 'Pending', { align: 'right' }),
    col('decided', 'Decided', { align: 'right' }),
    col('value', 'Pending value', { align: 'right', mono: true }),
  ],
};

const titled = (key) =>
  key.replace(/([A-Z])/g, ' $1').replace(/^./, (c) => c.toUpperCase());

export function columnsFor(tool, rows) {
  const present = new Set(rows.flatMap((r) => Object.keys(r)));
  const spec = (TOOL_COLUMNS[tool] || []).filter((c) => present.has(c.key));
  const known = new Set(spec.map((c) => c.key));
  const extra = [...present]
    .filter((k) => !known.has(k))
    .map((k) => col(k, titled(k)));
  return [...spec, ...extra];
}
