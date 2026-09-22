import { create } from 'zustand';

import { get } from '@/lib/apiClient';

const EMPTY = {
  state: null,
  header: null,
  draft: null,
  patternGroups: [],
  deltas: {},
  breakBooks: {},
  reasons: {},
  groupMeta: {},
  grounding: [],
  pipelineStages: [],
  pipelineStage: null,
  evidenceGaps: [],
  validationErrors: [],
  modelSkipped: null,
};

export const useFoboSessionStore = create((set, getState) => ({
  ...EMPTY,
  recId: null,
  loading: false,
  error: null,
  progress: null,

  setProgress: (progress) => set({ progress }),

  /**
   * Load one rec's case. Clears the previous rec first: leaving the old
   * analysis on screen while the next one loads shows a controller the
   * wrong rec's numbers under the right rec's name.
   */
  loadRec: async (recId) => {
    if (!recId || getState().loading) return;
    set({ ...EMPTY, recId, loading: true, error: null, progress: null });
    try {
      const d = await get(`/api/recs/${recId}`);
      set({
        state: d.state,
        header: d.header,
        draft: d.draft,
        patternGroups: d.pattern_groups,
        deltas: d.deltas,
        breakBooks: d.break_books,
        reasons: d.reasons,
        groupMeta: d.group_meta,
        grounding: d.grounding,
        pipelineStages: d.pipeline_stages,
        pipelineStage: d.pipeline_stage,
        evidenceGaps: d.evidence_gaps,
        validationErrors: d.validation_errors,
        modelSkipped: d.model_skipped,
        loading: false,
      });
    } catch (err) {
      set({ error: err.message, loading: false });
    }
  },
}));
