import { create } from 'zustand';

import { get } from '@/lib/apiClient';

export const useFoboTraceStore = create((set) => ({
  recId: null,
  trace: null,
  state: null,
  loading: false,
  error: null,

  loadTrace: async (recId) => {
    if (!recId) return;
    set({ recId, loading: true, error: null, trace: null });
    try {
      const d = await get(`/api/recs/${recId}/trace`);
      set({ trace: d.trace, state: d.state, loading: false });
    } catch (err) {
      set({ error: err.message, loading: false });
    }
  },
}));
