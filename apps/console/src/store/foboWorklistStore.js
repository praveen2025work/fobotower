import { create } from 'zustand';

import { get } from '@/lib/apiClient';

export const useFoboWorklistStore = create((set) => ({
  items: [],
  pending: 0,
  events: [],
  loading: false,
  error: null,

  load: async () => {
    set({ loading: true, error: null });
    try {
      const [work, activity] = await Promise.all([
        get('/api/worklist'),
        get('/api/activity'),
      ]);
      set({
        items: work.items,
        pending: work.pending,
        events: activity.events,
        loading: false,
      });
    } catch (err) {
      set({ error: err.message, loading: false });
    }
  },
}));
