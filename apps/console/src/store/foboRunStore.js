import { create } from 'zustand';

import { get } from '@/lib/apiClient';

export const useFoboRunStore = create((set) => ({
  regions: [],
  runWindows: [],
  stats: null,
  selectedRecId: null,
  defaultSessionId: null,
  loading: false,
  error: null,

  selectRec: (recId) => set({ selectedRecId: recId }),

  loadRuns: async () => {
    set({ loading: true, error: null });
    try {
      const data = await get('/api/runs');
      set({
        regions: data.regions,
        runWindows: data.run_windows,
        stats: data.stats,
        selectedRecId: data.default_rec_id,
        defaultSessionId: data.default_session_id,
        loading: false,
      });
    } catch (err) {
      set({ error: err.message, loading: false });
    }
  },
}));
