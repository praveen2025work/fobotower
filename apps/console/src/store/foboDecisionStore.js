import { create } from 'zustand';

import { post } from '@/lib/apiClient';

/** A fresh key per attempt. The server rejects a repeat with 409, so a
 *  retry after a network blip must carry a new one or it looks like a
 *  duplicate submission. */
function newKey() {
  return globalThis.crypto?.randomUUID?.() ?? `k-${Date.now()}-${Math.random()}`;
}

export const useFoboDecisionStore = create((set, getState) => ({
  // group_id or break_id -> 'approved' | 'rejected'
  decided: {},
  pending: null,
  error: null,

  reset: () => set({ decided: {}, pending: null, error: null }),

  decide: async ({ recId, action, groupId, breakId, reason }) => {
    const target = groupId ?? breakId;
    if (!target || getState().pending) return false;
    set({ pending: target, error: null });
    try {
      const res = await post(`/api/recs/${recId}/decisions`, {
        action,
        reason: reason ?? null,
        group_id: groupId ?? null,
        break_id: breakId ?? null,
      }, { 'Idempotency-Key': newKey() });

      const outcome = action === 'approve' ? 'approved' : 'rejected';
      const marks = { [target]: outcome };
      for (const b of res?.break_ids ?? []) marks[b] = outcome;
      set((s) => ({ decided: { ...s.decided, ...marks }, pending: null }));
      return true;
    } catch (err) {
      set({ error: err.message, pending: null });
      return false;
    }
  },
}));
