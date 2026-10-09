// Generated from apps/web/src/api/aof.ts by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see office/README.md.
// Types and TanStack Query hooks for the Agent One Finance API (apps/backend/agent_one_finance/web/main.py).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, newIdempotencyKey, upload } from "./client";

/** A team group: one team's configuration of a capability (e.g. a rec group). */
/** Why a group needs more than a click (agent_one_finance/review.py). */
/** One check a playbook ran on an item (e.g. FOBO's C1–C6); negatives are kept. */
/** One sign-off checklist question, with what Agent One Finance already knows (review.checklist). */
/** One entry of a skill session's conversation (the `agent` step). */
/** The skill session that produced the case's results. */
/** A question to a desk, a trader or Operations, and its answer. */
/** An open question addressed to the viewer, with just the rows it is about. */
/** A report the case's publish step wrote (e.g. a PDF), served by the API. */
const enc = encodeURIComponent;

export const useMe = (user) => useQuery({ queryKey: ["me", user], queryFn: () => api.get("/me"), enabled: !!user });
export const useDevUsers = () => useQuery({ queryKey: ["dev-users"], queryFn: () => api.get("/dev/users") });
export const useOverview = () => useQuery({ queryKey: ["overview"], queryFn: () => api.get("/overview") });
export const useInbox = () => useQuery({ queryKey: ["inbox"], queryFn: () => api.get("/inbox") });
export const useCapabilities = () => useQuery({ queryKey: ["capabilities"], queryFn: () => api.get("/capabilities") });
export const useCapability = (id) =>
  useQuery({ queryKey: ["capability", id], queryFn: () => api.get(`/capabilities/${enc(id)}`) });
export const useCases = (id, teamGroup) =>
  useQuery({
    queryKey: ["cases", id, teamGroup ?? "all"],
    queryFn: () => api.get(`/capabilities/${enc(id)}/cases${teamGroup ? `?team_group=${enc(teamGroup)}` : ""}`),
  });
export const useGroups = (id, enabled = true) =>
  useQuery({ queryKey: ["groups", id], queryFn: () => api.get(`/capabilities/${enc(id)}/groups`), enabled });
export const useGroup = (id, group) =>
  useQuery({
    queryKey: ["group", id, group],
    queryFn: () => api.get(`/capabilities/${enc(id)}/groups/${enc(group)}`),
  });
/** A case; while its run is in progress the view polls until it pauses or ends. */
export const useCase = (caseId) =>
  useQuery({
    queryKey: ["case", caseId],
    queryFn: () => api.get(`/cases/${enc(caseId)}`),
    refetchInterval: (q) => (q.state.data?.status === "running" ? 1500 : false),
  });
export const useMessages = (caseId) =>
  useQuery({ queryKey: ["messages", caseId], queryFn: () => api.get(`/cases/${enc(caseId)}/messages`) });
export const useHistory = (caseId, enabled = true) =>
  useQuery({ queryKey: ["history", caseId], queryFn: () => api.get(`/cases/${enc(caseId)}/history`), enabled });
export const useAudit = (capabilityId) =>
  useQuery({
    queryKey: ["audit", capabilityId ?? "all"],
    queryFn: () => api.get(`/audit${capabilityId ? `?capability_id=${enc(capabilityId)}` : ""}`),
  });
export const usePlatform = () => useQuery({ queryKey: ["platform"], queryFn: () => api.get("/platform") });

/** After anything that moves a case, refresh every view that summarises cases. */
function useRefreshCases() {
  const qc = useQueryClient();
  return (detail) => {
    if (detail) qc.setQueryData(["case", detail.case_id], detail);
    for (const key of ["inbox", "overview", "audit", "cases"]) qc.invalidateQueries({ queryKey: [key] });
  };
}

export function useOpenCase(capabilityId) {
  const refresh = useRefreshCases();
  return useMutation({
    mutationFn: (v) =>
      api.post(`/capabilities/${enc(capabilityId)}/cases`, {
        case_key: v.caseKey,
        team_group: v.teamGroup ?? null,
      }),
    onSuccess: (detail) => refresh(detail),
  });
}

export function useDecide(caseId) {
  const refresh = useRefreshCases();
  return useMutation({
    mutationFn: (v) =>
      api.post(`/cases/${enc(caseId)}/decisions`, {
        group_id: v.groupId,
        action: v.action,
        comment: v.comment || null,
        confirmed: v.confirmed ?? false,
        review_seconds: v.reviewSeconds ?? null,
        checklist: v.checklist ?? null,
        idempotency_key: newIdempotencyKey(),
      }),
    onSuccess: (res) => refresh(res.case),
  });
}

export function useRelease(caseId) {
  const refresh = useRefreshCases();
  return useMutation({
    mutationFn: () => api.post(`/cases/${enc(caseId)}/publish`, { idempotency_key: newIdempotencyKey() }),
    onSuccess: (res) => refresh(res.case),
  });
}

/** Ask a desk, a trader or Operations for evidence about a group or the case. */
export function useAskForEvidence(caseId) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v) => api.post(`/cases/${enc(caseId)}/requests`, v),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["case", caseId] }),
  });
}

export function useCancelRequest(caseId) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (requestId) => api.post(`/requests/${enc(requestId)}/cancel`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["case", caseId] }),
  });
}

export const useMyQuestions = () => useQuery({ queryKey: ["my-questions"], queryFn: () => api.get("/requests") });

export function useAnswerQuestion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v) => {
      if (!v.file) return api.post(`/requests/${enc(v.requestId)}/answer`, { answer: v.answer });
      const form = new FormData();
      form.append("answer", v.answer);
      form.append("file", v.file);
      return upload(`/requests/${enc(v.requestId)}/answer-with-file`, form);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["my-questions"] }),
  });
}

/** A person at a tollgate: continue the run, or stop it with a reason. */
export function usePassGate(caseId) {
  const refresh = useRefreshCases();
  return useMutation({
    mutationFn: (v) =>
      api.post(`/cases/${enc(caseId)}/gates/${enc(v.step)}`, {
        action: v.action,
        comment: v.comment,
        idempotency_key: newIdempotencyKey(),
      }),
    onSuccess: (detail) => refresh(detail),
  });
}

/** Deliver the event a case waits for, by hand (a person the `await` step names). */
export function useDeliverEvent(caseId) {
  const refresh = useRefreshCases();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v) => api.post(`/cases/${enc(caseId)}/events/${enc(v.step)}`, { payload: v.payload }),
    onSuccess: () => {
      refresh();
      qc.invalidateQueries({ queryKey: ["case", caseId] });
    },
  });
}

export function useBulkDecide(caseId) {
  const refresh = useRefreshCases();
  return useMutation({
    mutationFn: (v) =>
      api.post(`/cases/${enc(caseId)}/decisions/bulk`, {
        group_ids: v.groupIds,
        action: v.action,
        comment: v.comment || null,
        review_seconds: v.reviewSeconds ?? null,
        idempotency_key: newIdempotencyKey(),
      }),
    onSuccess: (res) => refresh(res.case),
  });
}

export function useReinvestigate(caseId) {
  const refresh = useRefreshCases();
  return useMutation({
    mutationFn: (v) =>
      api.post(`/cases/${enc(caseId)}/groups/${enc(v.groupId)}/reinvestigate`, {
        note: v.note,
        idempotency_key: newIdempotencyKey(),
      }),
    onSuccess: (res) => refresh(res.case),
  });
}

export function useRerun(caseId) {
  const refresh = useRefreshCases();
  return useMutation({
    mutationFn: () => api.post(`/cases/${enc(caseId)}/rerun`, {}),
    onSuccess: (detail) => refresh(detail),
  });
}

export function useRetryPublish(caseId) {
  const refresh = useRefreshCases();
  return useMutation({
    mutationFn: () => api.post(`/cases/${enc(caseId)}/publish/retry`, {}),
    onSuccess: (res) => refresh(res.case),
  });
}

export function useLegalHold(caseId) {
  const refresh = useRefreshCases();
  return useMutation({
    mutationFn: (v) => api.post(`/cases/${enc(caseId)}/legal-hold`, { hold: v.hold, reason: v.reason ?? null }),
    onSuccess: (detail) => refresh(detail),
  });
}

export function useAsk(caseId) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (question) => api.post(`/cases/${enc(caseId)}/ask`, { question }),
    onSuccess: (res) => qc.setQueryData(["messages", caseId], res.messages),
  });
}

// ---------- authoring (BRD → draft manifest) ----------

export const useDrafts = () => useQuery({ queryKey: ["drafts"], queryFn: () => api.get("/authoring/drafts") });

export const useAuthoringModes = () =>
  useQuery({ queryKey: ["authoring-modes"], queryFn: () => api.get("/authoring/modes") });
export const useGuidedDraft = () => useMutation({ mutationFn: (answers) => api.post("/authoring/guided", answers) });

export const useDraftFromBrd = () => useMutation({ mutationFn: (brd) => api.post("/authoring/draft", { brd }) });

export function useSubmitDraft() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v) => api.post("/authoring/submit", v),
    onSuccess: () => {
      for (const key of ["drafts", "capability"]) qc.invalidateQueries({ queryKey: [key] });
    },
  });
}

export function useApproveVersion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v) => api.post(`/capabilities/${enc(v.capabilityId)}/versions/${v.version}/approve`, {}),
    onSuccess: () => {
      for (const key of ["drafts", "capabilities", "capability", "overview"]) qc.invalidateQueries({ queryKey: [key] });
    },
  });
}

/** What a draft would be refused for, checked without storing anything. */
export function useConfigCheck(capabilityId, body) {
  const key = body ? JSON.stringify(body) : "";
  return useQuery({
    queryKey: ["config-check", capabilityId, key],
    queryFn: () => api.post(`/capabilities/${enc(capabilityId)}/check`, body),
    enabled: !!body,
    staleTime: 60_000,
    retry: false,
  });
}

// ---------- team groups ----------

export function useDraftGroup(capabilityId) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v) => api.post(`/capabilities/${enc(capabilityId)}/groups`, v),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["group"] }),
  });
}

export function useApproveGroup(capabilityId, group) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (version) =>
      api.post(`/capabilities/${enc(capabilityId)}/groups/${enc(group)}/versions/${version}/approve`, {}),
    onSuccess: () => {
      for (const key of ["group", "groups", "capabilities"]) qc.invalidateQueries({ queryKey: [key] });
    },
  });
}

// ---------- notifications ----------

export const useNotifications = (enabled = true) =>
  useQuery({
    queryKey: ["notifications"],
    queryFn: () => api.get("/notifications"),
    refetchInterval: 30_000,
    enabled,
  });

export function useMarkRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ids) => api.post("/notifications/read", { ids }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });
}

// ---------- run-the-bank: schedules, switches ----------

export const useSchedules = () => useQuery({ queryKey: ["schedules"], queryFn: () => api.get("/schedules") });
export const useSwitches = () => useQuery({ queryKey: ["switches"], queryFn: () => api.get("/switches") });

export function useSetSwitch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v) => api.post("/switches", v),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["switches"] }),
  });
}

// ---------- evidence ----------

export function useUploadEvidence(caseId) {
  const refresh = useRefreshCases();
  return useMutation({
    mutationFn: async (v) => {
      const form = new FormData();
      form.append("file", v.file);
      if (v.note) form.append("note", v.note);
      return upload(`/cases/${enc(caseId)}/evidence`, form);
    },
    onSuccess: (res) => refresh(res.case),
  });
}

// ---------- evals ----------

export const useEvals = (id) =>
  useQuery({
    queryKey: ["evals", id],
    queryFn: () => api.get(`/capabilities/${enc(id)}/evals`),
    refetchInterval: (q) => (q.state.data?.some((r) => r.status === "running") ? 2000 : false),
  });

/** How many past settled cases an eval would replay. */
export const useEvalAvailable = (id, teamGroup) =>
  useQuery({
    queryKey: ["evals-available", id, teamGroup ?? ""],
    queryFn: () =>
      api.get(`/capabilities/${enc(id)}/evals/available${teamGroup ? `?team_group=${enc(teamGroup)}` : ""}`),
    retry: false,
  });

/** One eval run with what each replayed case produced. */
export const useEvalRun = (runId) =>
  useQuery({
    queryKey: ["eval", runId],
    queryFn: () => api.get(`/evals/${enc(runId)}`),
    enabled: !!runId,
  });

export function useStartEval(id) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v) => api.post(`/capabilities/${enc(id)}/evals`, v),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["evals", id] }),
  });
}

// ---------- developer tools ----------

export const useFlow = (id, teamGroup) =>
  useQuery({
    queryKey: ["flow", id, teamGroup ?? ""],
    queryFn: () => api.get(`/capabilities/${enc(id)}/flow${teamGroup ? `?team_group=${enc(teamGroup)}` : ""}`),
  });

export const useDiff = (id, a, b, group) =>
  useQuery({
    queryKey: ["diff", id, group ?? "", a, b],
    queryFn: () =>
      api.get(
        group
          ? `/capabilities/${enc(id)}/groups/${enc(group)}/versions/${a}/diff/${b}`
          : `/capabilities/${enc(id)}/versions/${a}/diff/${b}`,
      ),
    enabled: a != null && b != null && a !== b,
  });

export const useTemplates = () => useQuery({ queryKey: ["templates"], queryFn: () => api.get("/authoring/templates") });

export function useImportBundle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (bundle) => api.post("/promotion/import", { bundle }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["drafts"] }),
  });
}

// ---------- recurring items, delegation ----------

export const useRecurring = (id, teamGroup, enabled = true) =>
  useQuery({
    queryKey: ["recurring", id, teamGroup ?? "all"],
    queryFn: () => api.get(`/capabilities/${enc(id)}/recurring${teamGroup ? `?team_group=${enc(teamGroup)}` : ""}`),
    enabled,
  });

/** The data a configuration reads, and the parameters still to confirm. */
export const useDataContract = (id, teamGroup) =>
  useQuery({
    queryKey: ["contract", id, teamGroup ?? "all"],
    queryFn: () => api.get(`/capabilities/${enc(id)}/contract${teamGroup ? `?team_group=${enc(teamGroup)}` : ""}`),
  });

/** What nothing explained, and model-proposed groups reviewers keep approving unchanged. */
export const useLearning = (id, teamGroup) =>
  useQuery({
    queryKey: ["learning", id, teamGroup ?? "all"],
    queryFn: () => api.get(`/capabilities/${enc(id)}/learning${teamGroup ? `?team_group=${enc(teamGroup)}` : ""}`),
  });

export const useDelegations = () =>
  useQuery({
    queryKey: ["delegations"],
    queryFn: () => api.get("/me/delegations"),
  });

export function useDelegate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v) => api.post("/me/delegations", { to_user: v.toUser, until: v.until, reason: v.reason || null }),
    onSuccess: () => {
      for (const key of ["delegations", "inbox", "me"]) qc.invalidateQueries({ queryKey: [key] });
    },
  });
}

export function useEndDelegation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) => api.del(`/me/delegations/${enc(id)}`),
    onSuccess: () => {
      for (const key of ["delegations", "inbox", "me"]) qc.invalidateQueries({ queryKey: [key] });
    },
  });
}
