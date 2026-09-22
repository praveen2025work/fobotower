import { create } from 'zustand';

import { get, post } from '@/lib/apiClient';

export const useFoboSessionStore = create((set) => ({
  session: null,
  draft: null,
  patternGroups: [],
  deltas: {},
  breakBooks: {},
  pipelineStages: [],
  pipelineStage: null,
  evidenceGaps: [],
  validationErrors: [],
  modelSkipped: null,
  progress: null,
  loading: false,
  error: null,

  setProgress: (progress) => set({ progress }),

  investigate: async (sessionId) => {
    set({ loading: true, error: null });
    try {
      await post(`/api/sessions/${sessionId}/investigate`);
      const data = await get(`/api/sessions/${sessionId}`);
      set({
        session: data.session,
        draft: data.draft,
        patternGroups: data.pattern_groups,
        deltas: data.deltas,
        breakBooks: data.break_books,
        pipelineStages: data.pipeline_stages,
        pipelineStage: data.pipeline_stage,
        evidenceGaps: data.evidence_gaps,
        validationErrors: data.validation_errors,
        modelSkipped: data.model_skipped,
        loading: false,
      });
    } catch (err) {
      set({ error: err.message, loading: false });
    }
  },
}));
