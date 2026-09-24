import { columnsFor } from '../lib/mcpColumns';

/**
 * The API serves calls as recorded. The call components also want the table
 * columns and a printable latency, so those are added here, once, on arrival.
 */
export function adaptCall(call) {
  const rows = call.rows || [];
  return {
    ...call,
    rows,
    columns: columnsFor(call.tool, rows),
    // 0 is a real measurement, but `{0 && ...}` would print a bare "0".
    ms: call.ms === 0 ? '<1' : call.ms,
  };
}

export const adaptMessage = (m) =>
  m.calls ? { ...m, calls: m.calls.map(adaptCall) } : m;

export const adaptRec = (rec) => ({
  ...rec,
  calls: (rec.calls || []).map(adaptCall),
  session: (rec.session || []).map(adaptMessage),
});
