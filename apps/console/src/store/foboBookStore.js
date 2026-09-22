import { create } from 'zustand';

import { get } from '@/lib/apiClient';

export const useFoboBookStore = create((set) => ({
  data: null,
  loading: false,
  error: null,

  clear: () => set({ data: null, loading: false, error: null }),

  load: async (bookRef) => {
    set({ data: null, loading: true, error: null });
    try {
      set({ data: await get(`/api/books/${bookRef}`), loading: false });
    } catch (err) {
      set({ error: err.message, loading: false });
    }
  },
}));
