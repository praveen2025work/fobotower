export const bookCounts = (b) => ({
  needsAnalysis: b.total - b.autoPost,
  open: b.cleared + b.awaiting + b.analysing + b.blocked,
});

export const amt = (a) => Number(String(a.amount).replace(/[$,]/g, ''));

export const money = (n, ccy = 'USD') =>
  `${ccy} ${Number(n).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;

export const money0 = (n, ccy = 'USD') =>
  `${ccy} ${Math.round(n).toLocaleString('en-US')}`;

/** The orchestrator's own session id, so what the controller reads is what
 *  the audit trail records. */
export const sessionIdOf = (rec) => rec.sessionId || `HLX-${rec.id}`;

export const groundingRate = (rec) =>
  rec.adjustments.length
    ? (rec.adjustments.filter((a) => a.grounded).length /
        rec.adjustments.length) *
      100
    : null;

export const mono = {
  fontFamily: 'var(--hx-font-mono), monospace',
};

export const manrope = {
  fontFamily: 'var(--hx-font-manrope), sans-serif',
};

/** Wall-clock IST, for a message shown before the server has answered. */
export const nowStamp = () =>
  new Date().toLocaleTimeString('en-GB', {
    timeZone: 'Asia/Kolkata',
    hour: '2-digit',
    minute: '2-digit',
  });
