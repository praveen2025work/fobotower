import { create } from 'zustand';

import { get } from '@/lib/apiClient';

export const useFoboAnalyticsStore = create((set) => ({
  data: null,
  loading: false,
  error: null,

  load: async () => {
    set({ loading: true, error: null });
    try {
      set({ data: await get('/api/analytics'), loading: false });
    } catch (err) {
      set({ error: err.message, loading: false });
    }
  },
}));
