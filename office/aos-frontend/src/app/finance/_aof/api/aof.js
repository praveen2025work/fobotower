// Generated from apps/web/src/api/aof.ts by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see office/README.md.
// Types and TanStack Query hooks for the Agent One Finance API (apps/backend/agent_one_finance/web/main.py).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, newIdempotencyKey, upload } from "./client";

/** A team group: one team's configuration of an agent (e.g. a rec group). */
/** Why a group needs more than a click (agent_one_finance/review.py). */
/** One check a playbook ran on an item (e.g. FOBO's C1–C6); negatives are kept. */
/** One sign-off checklist question, with what Agent One Finance already knows (review.checklist). */
/** One entry of a skill session's conversation (the `agent` step). */
/** The skill session that produced the task's results. */
/** A question to a desk, a trader or Operations, and its answer. */
/** An open question addressed to the viewer, with just the rows it is about. */
/** A report the task's publish step wrote (e.g. a PDF), served by the API. */
const enc = encodeURIComponent;

export const useMe = (user) => useQuery({ queryKey: ["me", user], queryFn: () => api.get("/me"), enabled: !!user });
export const useDevUsers = () => useQuery({ queryKey: ["dev-users"], queryFn: () => api.get("/dev/users") });
export const useOverview = () => useQuery({ queryKey: ["overview"], queryFn: () => api.get("/overview") });
export const useInbox = () => useQuery({ queryKey: ["inbox"], queryFn: () => api.get("/inbox") });
export const useAgents = () => useQuery({ queryKey: ["agents"], queryFn: () => api.get("/agents") });
export const useAgent = (id) => useQuery({ queryKey: ["agent", id], queryFn: () => api.get(`/agents/${enc(id)}`) });
export const useCases = (id, teamGroup) =>
  useQuery({
    queryKey: ["tasks", id, teamGroup ?? "all"],
    queryFn: () => api.get(`/agents/${enc(id)}/tasks${teamGroup ? `?team_group=${enc(teamGroup)}` : ""}`),
  });
export const useGroups = (id, enabled = true) =>
  useQuery({ queryKey: ["groups", id], queryFn: () => api.get(`/agents/${enc(id)}/groups`), enabled });
export const useGroup = (id, group) =>
  useQuery({
    queryKey: ["group", id, group],
    queryFn: () => api.get(`/agents/${enc(id)}/groups/${enc(group)}`),
  });
/** A task; while its run is in progress the view polls until it pauses or ends. */
export const useCase = (taskId) =>
  useQuery({
    queryKey: ["task", taskId],
    queryFn: () => api.get(`/tasks/${enc(taskId)}`),
    refetchInterval: (q) => (q.state.data?.status === "running" ? 1500 : false),
  });
export const useMessages = (taskId) =>
  useQuery({ queryKey: ["messages", taskId], queryFn: () => api.get(`/tasks/${enc(taskId)}/messages`) });
export const useHistory = (taskId, enabled = true) =>
  useQuery({ queryKey: ["history", taskId], queryFn: () => api.get(`/tasks/${enc(taskId)}/history`), enabled });
export const useAudit = (agentId) =>
  useQuery({
    queryKey: ["audit", agentId ?? "all"],
    queryFn: () => api.get(`/audit${agentId ? `?agent_id=${enc(agentId)}` : ""}`),
  });
export const usePlatform = () => useQuery({ queryKey: ["platform"], queryFn: () => api.get("/platform") });

/** After anything that moves a task, refresh every view that summarises tasks. */
function useRefreshTasks() {
  const qc = useQueryClient();
  return (detail) => {
    if (detail) qc.setQueryData(["task", detail.task_id], detail);
    for (const key of ["inbox", "overview", "audit", "tasks"]) qc.invalidateQueries({ queryKey: [key] });
  };
}

export function useOpenTask(agentId) {
  const refresh = useRefreshTasks();
  return useMutation({
    mutationFn: (v) =>
      api.post(`/agents/${enc(agentId)}/tasks`, {
        task_key: v.taskKey,
        team_group: v.teamGroup ?? null,
      }),
    onSuccess: (detail) => refresh(detail),
  });
}

export function useDecide(taskId) {
  const refresh = useRefreshTasks();
  return useMutation({
    mutationFn: (v) =>
      api.post(`/tasks/${enc(taskId)}/decisions`, {
        group_id: v.groupId,
        action: v.action,
        comment: v.comment || null,
        confirmed: v.confirmed ?? false,
        review_seconds: v.reviewSeconds ?? null,
        checklist: v.checklist ?? null,
        idempotency_key: newIdempotencyKey(),
      }),
    onSuccess: (res) => refresh(res.task),
  });
}

export function useRelease(taskId) {
  const refresh = useRefreshTasks();
  return useMutation({
    mutationFn: () => api.post(`/tasks/${enc(taskId)}/publish`, { idempotency_key: newIdempotencyKey() }),
    onSuccess: (res) => refresh(res.task),
  });
}

/** Ask a desk, a trader or Operations for evidence about a group or the task. */
export function useAskForEvidence(taskId) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v) => api.post(`/tasks/${enc(taskId)}/requests`, v),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["task", taskId] }),
  });
}

export function useCancelRequest(taskId) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (requestId) => api.post(`/requests/${enc(requestId)}/cancel`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["task", taskId] }),
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
export function usePassGate(taskId) {
  const refresh = useRefreshTasks();
  return useMutation({
    mutationFn: (v) =>
      api.post(`/tasks/${enc(taskId)}/gates/${enc(v.step)}`, {
        action: v.action,
        comment: v.comment,
        idempotency_key: newIdempotencyKey(),
      }),
    onSuccess: (detail) => refresh(detail),
  });
}

/** Deliver the event a task waits for, by hand (a person the `await` step names). */
export function useDeliverEvent(taskId) {
  const refresh = useRefreshTasks();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v) => api.post(`/tasks/${enc(taskId)}/events/${enc(v.step)}`, { payload: v.payload }),
    onSuccess: () => {
      refresh();
      qc.invalidateQueries({ queryKey: ["task", taskId] });
    },
  });
}

export function useBulkDecide(taskId) {
  const refresh = useRefreshTasks();
  return useMutation({
    mutationFn: (v) =>
      api.post(`/tasks/${enc(taskId)}/decisions/bulk`, {
        group_ids: v.groupIds,
        action: v.action,
        comment: v.comment || null,
        review_seconds: v.reviewSeconds ?? null,
        idempotency_key: newIdempotencyKey(),
      }),
    onSuccess: (res) => refresh(res.task),
  });
}

export function useReinvestigate(taskId) {
  const refresh = useRefreshTasks();
  return useMutation({
    mutationFn: (v) =>
      api.post(`/tasks/${enc(taskId)}/groups/${enc(v.groupId)}/reinvestigate`, {
        note: v.note,
        idempotency_key: newIdempotencyKey(),
      }),
    onSuccess: (res) => refresh(res.task),
  });
}

export function useRerun(taskId) {
  const refresh = useRefreshTasks();
  return useMutation({
    mutationFn: () => api.post(`/tasks/${enc(taskId)}/rerun`, {}),
    onSuccess: (detail) => refresh(detail),
  });
}

export function useRetryPublish(taskId) {
  const refresh = useRefreshTasks();
  return useMutation({
    mutationFn: () => api.post(`/tasks/${enc(taskId)}/publish/retry`, {}),
    onSuccess: (res) => refresh(res.task),
  });
}

export function useLegalHold(taskId) {
  const refresh = useRefreshTasks();
  return useMutation({
    mutationFn: (v) => api.post(`/tasks/${enc(taskId)}/legal-hold`, { hold: v.hold, reason: v.reason ?? null }),
    onSuccess: (detail) => refresh(detail),
  });
}

export function useAsk(taskId) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (question) => api.post(`/tasks/${enc(taskId)}/ask`, { question }),
    onSuccess: (res) => qc.setQueryData(["messages", taskId], res.messages),
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
      for (const key of ["drafts", "agent"]) qc.invalidateQueries({ queryKey: [key] });
    },
  });
}

export function useApproveVersion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v) => api.post(`/agents/${enc(v.agentId)}/versions/${v.version}/approve`, {}),
    onSuccess: () => {
      for (const key of ["drafts", "agents", "agent", "overview"]) qc.invalidateQueries({ queryKey: [key] });
    },
  });
}

/** What a draft would be refused for, checked without storing anything. */
export function useConfigCheck(agentId, body) {
  const key = body ? JSON.stringify(body) : "";
  return useQuery({
    queryKey: ["config-check", agentId, key],
    queryFn: () => api.post(`/agents/${enc(agentId)}/check`, body),
    enabled: !!body,
    staleTime: 60_000,
    retry: false,
  });
}

// ---------- team groups ----------

export function useDraftGroup(agentId) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v) => api.post(`/agents/${enc(agentId)}/groups`, v),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["group"] }),
  });
}

export function useApproveGroup(agentId, group) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (version) => api.post(`/agents/${enc(agentId)}/groups/${enc(group)}/versions/${version}/approve`, {}),
    onSuccess: () => {
      for (const key of ["group", "groups", "agents"]) qc.invalidateQueries({ queryKey: [key] });
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

export function useUploadEvidence(taskId) {
  const refresh = useRefreshTasks();
  return useMutation({
    mutationFn: async (v) => {
      const form = new FormData();
      form.append("file", v.file);
      if (v.note) form.append("note", v.note);
      return upload(`/tasks/${enc(taskId)}/evidence`, form);
    },
    onSuccess: (res) => refresh(res.task),
  });
}

// ---------- evals ----------

export const useEvals = (id) =>
  useQuery({
    queryKey: ["evals", id],
    queryFn: () => api.get(`/agents/${enc(id)}/evals`),
    refetchInterval: (q) => (q.state.data?.some((r) => r.status === "running") ? 2000 : false),
  });

/** How many past settled tasks an eval would replay. */
export const useEvalAvailable = (id, teamGroup) =>
  useQuery({
    queryKey: ["evals-available", id, teamGroup ?? ""],
    queryFn: () => api.get(`/agents/${enc(id)}/evals/available${teamGroup ? `?team_group=${enc(teamGroup)}` : ""}`),
    retry: false,
  });

/** One eval run with what each replayed task produced. */
export const useEvalRun = (runId) =>
  useQuery({
    queryKey: ["eval", runId],
    queryFn: () => api.get(`/evals/${enc(runId)}`),
    enabled: !!runId,
  });

export function useStartEval(id) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v) => api.post(`/agents/${enc(id)}/evals`, v),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["evals", id] }),
  });
}

// ---------- developer tools ----------

export const useFlow = (id, teamGroup) =>
  useQuery({
    queryKey: ["flow", id, teamGroup ?? ""],
    queryFn: () => api.get(`/agents/${enc(id)}/flow${teamGroup ? `?team_group=${enc(teamGroup)}` : ""}`),
  });

export const useDiff = (id, a, b, group) =>
  useQuery({
    queryKey: ["diff", id, group ?? "", a, b],
    queryFn: () =>
      api.get(
        group
          ? `/agents/${enc(id)}/groups/${enc(group)}/versions/${a}/diff/${b}`
          : `/agents/${enc(id)}/versions/${a}/diff/${b}`,
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
    queryFn: () => api.get(`/agents/${enc(id)}/recurring${teamGroup ? `?team_group=${enc(teamGroup)}` : ""}`),
    enabled,
  });

/** The data a configuration reads, and the parameters still to confirm. */
export const useDataContract = (id, teamGroup) =>
  useQuery({
    queryKey: ["contract", id, teamGroup ?? "all"],
    queryFn: () => api.get(`/agents/${enc(id)}/contract${teamGroup ? `?team_group=${enc(teamGroup)}` : ""}`),
  });

/** What nothing explained, and model-proposed groups reviewers keep approving unchanged. */
export const useLearning = (id, teamGroup) =>
  useQuery({
    queryKey: ["learning", id, teamGroup ?? "all"],
    queryFn: () => api.get(`/agents/${enc(id)}/learning${teamGroup ? `?team_group=${enc(teamGroup)}` : ""}`),
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
