// Types and TanStack Query hooks for the Agent One Finance API (apps/backend/agent_one_finance/web/main.py).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, newIdempotencyKey, upload } from "./client";

export type TaskStatus =
  | "running"
  | "awaiting_review"
  | "awaiting_publish"
  | "completed"
  | "escalated"
  | "failed"
  | string;

export interface Me {
  user_id: string;
  roles: string[];
  data_scopes: Record<string, string[]>;
  llm: string;
  /** Platform support: sees platform details (LLM, entitlement source). */
  is_admin?: boolean;
  /** Colleagues this user is covering reviews for right now. */
  covering_for?: string[];
}

export interface DevUser {
  user_id: string;
  name?: string;
  roles: string[];
}

export interface AgentSummary {
  id: string;
  name: string;
  description: string;
  version: number;
  task_label: string;
  item_label: string;
  task_key: string[];
  steps: string[];
  is_owner: boolean;
  can_decide: boolean;
  configurable: string[];
  groups: { group: string; name: string }[];
}

/** A team group: one team's configuration of an agent (e.g. a rec group). */
export interface TeamGroup {
  agent_id: string;
  group: string;
  name: string;
  description: string;
  version: number;
  owners: { people: string[]; role: string | null; four_eyes: boolean };
  sets: string[];
  task_label: string;
  item_label: string;
  task_key: string[];
  review_roles: string[];
  is_owner: boolean;
  can_open: boolean;
  can_decide: boolean;
}

export interface GroupConfig {
  group: string;
  name: string;
  description: string;
  owners: { people: string[]; role: string | null; four_eyes: boolean };
  set: Record<string, unknown>;
}

export interface TeamGroupDetail extends TeamGroup {
  config: GroupConfig;
  manifest: Manifest;
  configurable: string[];
  versions: (AgentVersion & { config: GroupConfig })[];
}

export interface Manifest {
  id: string;
  name: string;
  description: string;
  owners: { people: string[]; role: string | null; four_eyes: boolean };
  task: { label: string; item_label: string; key: string[]; subject: string | null; scopes: Record<string, string>; opens_on: string };
  items: { load: { tool: string; args: Record<string, unknown> } | null; id_field: string; amount_field: string | null; display: string[]; in_scope: string | null };
  steps: string[];
  pause_before: string[];
  group_by: string[];
  policy: Record<string, { value: unknown; unit: string | null }>;
  rules: { id: string; when: string; then: { status: string; comment: string } }[];
  reasoning: { reasoner: string; skill: string; tools: string[]; output: string };
  review: { roles: string[] };
  publish: { tool: string; args: Record<string, unknown>; approver_roles: string[] } | null;
  match?: { left: { tool: string }; right: { tool: string }; keys: string[] } | null;
  configurable: string[];
}

export interface AgentVersion {
  version: number;
  status: string;
  note: string;
  drafted_by: string;
  drafted_at: string;
  decided_by: string | null;
  decided_at: string | null;
}

export interface AgentDetail {
  version: number;
  manifest: Manifest;
  versions: AgentVersion[];
}

export interface TaskSummary {
  task_id: string;
  agent_id: string;
  subject: string;
  task_key: Record<string, string>;
  status: TaskStatus;
  outcome: string | null;
  manifest_version: number;
  team_group: string | null;
  team_group_version: number | null;
  opened_by: string;
  opened_at: string;
  trace_id: string | null;
  error: string | null;
  attempt: number;
  rerun_of: string | null;
  legal_hold: boolean;
  due_at?: string | null;
  review_ready_at?: string | null;
}

/** Why a group needs more than a click (agent_one_finance/review.py). */
export type ReviewFlag = "confirmation" | "judgement" | "escalated" | "model";
export type DueState = "on_time" | "due_soon" | "overdue" | null;

/** One check a playbook ran on an item (e.g. FOBO's C1–C6); negatives are kept. */
export interface CheckResult {
  id: string;
  positive: boolean;
  reason: string;
}

export interface Finding {
  status: "proposed" | "escalated";
  decided_by: string;
  comment: string;
  reason?: string | null;
  rule?: string;
  model?: string | null;
  usage?: { cost_usd?: number | null; turns?: number | null; input_tokens?: number | null; output_tokens?: number | null };
  // playbook agents (e.g. FOBO): what the playbook says about the group
  verdict?: string | null;
  category?: string | null;
  category_name?: string | null;
  side?: string | null;
  /** The side in business words (playbook.side_names). */
  side_name?: string | null;
  escalate_to?: string | null;
  determinism?: string | null;
  requires_confirmation?: string;
  guard?: string;
  sme_review?: boolean;
  // a reviewer sent it back to the model
  reinvestigations?: number;
  reviewer_note?: string;
  previous?: { status: string; comment: string; reason: string | null; decided_by: string };
  /** The model's answer in the configured parts (reasoning.sections). */
  sections?: { id: string; label: string; text: string }[];
  // steps v2
  /** The authority tier: who may approve, how many different people, the review lane. */
  authority?: { label: string; roles: string[]; approvals: number; lane: string; bulk: boolean; source: string };
  /** A decision reserved for named people (a boundary). */
  reserved?: { roles: string[]; reason: string };
  /** What the model proposed but may not (a boundary): withheld for a person. */
  withheld_proposal?: string | null;
  /** Balanced journals proposed for the group (propose_entries). */
  entries?: JournalProposal;
  /** The outbound message drafted for the group (compose), and what was sent (outreach). */
  draft_message?: OutboundMessage;
  sent_message?: OutboundMessage & { message_id?: string | null; approved_by?: string | null; error?: string };
}

export interface JournalProposal {
  journal_id: string;
  period: string | null;
  lines: { account: string; side: "debit" | "credit"; amount: number; cost_centre?: string; narrative?: string }[];
  debits: number;
  credits: number;
  balanced: boolean;
  problems: string[];
}
export interface OutboundMessage { to: string; subject: string; body: string; step?: string }

/** One sign-off checklist question, with what Agent One Finance already knows (review.checklist). */
export interface ChecklistQuestion {
  id: string;
  label: string;
  required: boolean;
  known: string;
}
export type ChecklistAnswer = { id: string; label?: string; answer: "yes" | "no" | "n/a" | null; note?: string | null };

export interface Group {
  group_id: string;
  label: string;
  group_key: Record<string, string>;
  item_ids: string[];
  priors: { comment: string; task_id: string; decided_by: string; at: string; match?: string }[];
  finding: Finding | null;
  decision: {
    action: "approve" | "reject";
    comment: string | null;
    decided_by: string;
    decided_at: string;
    on_behalf_of?: string | null;
    confirmed?: boolean;
    checklist?: ChecklistAnswer[] | null;
  } | null;
  /** The sign-off checklist for this group, prefilled. */
  checklist?: ChecklistQuestion[] | null;
  flags?: ReviewFlag[];
  /** Flags that keep this group out of "Approve all" (review.bulk_exclude). */
  bulk_blockers?: ReviewFlag[];
  /** Different people who must approve (dual review, authority tier), who has, and whether it is settled. */
  approvals?: { needed: number; by: string[]; settled: boolean };
  /** The ticket raised for the owning team (manifest `escalation`). */
  ticket?: { reference: string | null; url: string | null; status: "raised" | "failed"; error: string | null; raised_at: string } | null;
}

export interface ToolCall {
  call_id: string;
  tool: string;
  connector_id: string;
  requested_by: string;
  caller: string;
  arguments: Record<string, unknown>;
  allowed: boolean;
  denied_reason: string | null;
  row_count: number | null;
  error: string | null;
  latency_ms: number | null;
  called_at: string;
}

/** One entry of a skill session's conversation (the `agent` step). */
export interface SessionTurn {
  turn: number;
  role: "user" | "model" | "tool";
  kind: "prompt" | "text" | "tool_call" | "tool_result" | "answer";
  text?: string;
  tool?: string;
  input?: Record<string, unknown>;
  rows?: number | null;
  error?: boolean;
}

/** The skill session that produced the task's results. */
export interface SessionInfo {
  adapter: string;
  model: string | null;
  skill_file: string | null;
  skill_chars: number;
  tools: string[];
  results: number;
  failure: string | null;
  session_id?: string;
  turns?: number;
  cost_usd?: number;
  duration_ms?: number;
  transcript: SessionTurn[];
}

/** One row of a task's Summary breakdown (a desk, a product in it, a book in that), with the rows a level down. */
export interface SummaryRow {
  field: string;
  value: string;
  items: number;
  net?: number;
  gross?: number;
  /** distinct values of the deeper fields, e.g. { book: 82 } */
  distinct: Record<string, number>;
  proposals: { group_id: string; items: number }[];
  open: number;
  children: SummaryRow[];
}

export interface ModelUsage {
  input_tokens?: number;
  output_tokens?: number;
  cost_usd?: number;
  turns?: number;
  duration_ms?: number;
}

/** Who decided what on a task, and the model session behind it. */
export interface ModelSessionInfo {
  decided_by: Record<string, number>;
  adapters: string[];
  models: string[];
  groups: ({ group_id: string; label: string; model: string | null; status: string | null; reason: string | null; session_id?: string } & ModelUsage)[];
  usage: ModelUsage;
  chat: { answers: number; usage: ModelUsage };
  limits: { max_cost_usd_per_task: number | null; max_cost_usd_per_day: number | null };
  lookups: { count: number; refused: number; by_tool: Record<string, number> };
  tools: string[];
  specialists: { name: string; description: string; tools: string[] }[];
  instructions_chars: number;
  skill_session: (ModelUsage & { adapter?: string; model?: string; skill_file?: string; results?: number; failure?: string; session_id?: string }) | null;
}

/** GET /tasks/{id}/summary: what a task read and found, broken down by task.summarize_by. */
export interface TaskSummaryView {
  task_id: string;
  subject: string;
  status: string;
  outcome: string | null;
  item_label: string;
  unit: string | null;
  amount_field: string | null;
  by: string[];
  sources: { tool: string; step: string; arguments: Record<string, unknown>; rows: number | null; distinct: Record<string, number>; without_items: Record<string, number> }[];
  items: { count: number; in_proposals: number; open: number; net?: number; gross?: number; distinct: Record<string, number> };
  breakdown: SummaryRow[];
  proposals: {
    group_id: string;
    label: string;
    items: number;
    net?: number;
    gross?: number;
    distinct: Record<string, number>;
    status: string | null;
    verdict: string | null;
    decided_by: string | null;
    escalate_to: string | null;
    flags: ReviewFlag[];
    decision: { action: string; by: string; at: string } | null;
  }[];
  model: ModelSessionInfo;
}

export interface TaskDetail extends TaskSummary {
  /** what the Summary tab breaks the task's items down by (task.summarize_by); empty = not summarised */
  summarize_by?: string[];
  draft: { headline: string; summary?: string; skipped_steps?: string[]; session?: SessionInfo } | null;
  labels: { task: string; item: string; agent?: string };
  steps: string[];
  pause_before: string[];
  columns: string[];
  items: ({ item_id: string; in_scope: boolean } & Record<string, unknown>)[];
  groups: Group[];
  decisions: { group_id: string; action: string; comment: string | null; decided_by: string; decided_at: string }[];
  tool_calls: ToolCall[];
  documents: PublishedDocument[];
  evidence?: Evidence[];
  attempts: { task_id: string; attempt: number; status: TaskStatus; outcome: string | null; opened_by: string; opened_at: string }[];
  can_decide: boolean;
  /** Deciding on behalf of this absent colleague (delegation). */
  acting_for?: string | null;
  due_state?: DueState;
  exposure?: number | null;
  unit?: string | null;
  id_field?: string;
  amount_field?: string | null;
  /** item_id -> how often it has come back (insights.recurring). */
  recurring?: Record<string, { runs: number; earlier: { task_id: string; subject: string; opened_at: string }[] }>;
  can_rerun: boolean;
  can_retry_publish: boolean;
  can_hold: boolean;
  legal_hold_reason: string | null;
  review: {
    require_comment: ("reject" | "escalated")[];
    opener_may_decide: boolean;
    dual_review_when: string | null;
    max_reinvestigations: number;
    bulk_exclude?: ReviewFlag[];
    confirm?: "none" | "tick" | "tick_and_comment";
    allow_delegation?: boolean;
    roles?: string[];
    checklist?: { id: string; label: string; required: boolean; prefill: string | null }[];
  };
  publish: {
    tool: string;
    approver_roles: string[];
    can_release: boolean;
    per?: "group" | "task";
    released?: { by: string; at: string } | null;
  } | null;
  /** Who the task waits on; when it is not the viewer, why not. */
  waiting_on?: {
    step: "review" | "release" | "gate" | "event";
    /** Waiting at an `await` step: the event, since when, its timeout. */
    event?: string;
    wait?: string;
    label?: string;
    since?: string | null;
    timeout_hours?: number | null;
    on_timeout?: string | null;
    roles: string[];
    you: boolean;
    why_not: string | null;
    reviewed_by?: string[];
    gate?: string;                 // the step a tollgate stands before
    check?: string;                // what the person checks there
    stop_needs_comment?: boolean;
  } | null;
  /** A follow-up for late items: the day's task it follows; and the follow-ups of this task. */
  follow_up_of?: string | null;
  follow_ups?: { task_id: string; subject: string; status: string; outcome: string | null; opened_at: string; items?: number }[];
  /** Questions asked for evidence, who may be asked, and whether the viewer may ask. */
  requests?: InfoRequest[];
  request_targets?: { id: string; name: string }[];
  can_ask?: boolean;
  /** The agent's tollgates: human stops before steps other than review and publish. */
  tollgates?: { step: string; roles: string[]; check: string }[];
  gate_decisions?: { step: string; action: "continue" | "stop"; comment: string | null; decided_by: string; decided_at: string }[];
  /** What became of this task's decisions in the next run of its series (follow_through). */
  follow_through?: {
    cleared: number;
    still_open: number;
    items: { item_id: string; verdict: string | null; status: "cleared" | "still_open"; checked_in: string; checked_at: string }[];
  } | null;
  follow_through_spec?: { series: string[]; order_by: string; verdicts: string[] } | null;
  /** Named data sets the run read or built beside the items (steps v2). */
  datasets?: { name: string; step_id: string; source: string; row_count: number; columns: string[]; rows: Record<string, unknown>[] }[];
  /** Items a step set aside (filter, duplicates, roll-up), with why. */
  excluded?: { item_id: string; by: string; reason: string }[];
  step_labels?: Record<string, string>;
  step_types?: Record<string, string>;
  /** The task that opened this one (a `spawn` step), and the tasks this one opened. */
  parent_task_id?: string | null;
  children?: { task_id: string; subject: string; status: TaskStatus; outcome: string | null; agent_id: string }[];
  /** Service-level or regulatory clocks (a `clock` step), earliest per clock. */
  clocks?: { id: string; label: string; due_at: string; warn_before_hours: number; warned: boolean; breached: boolean }[];
}

/** A question to a desk, a trader or Operations, and its answer. */
export interface InfoRequest {
  request_id: string;
  task_id: string;
  group_id: string | null;
  target: string;
  target_name: string;
  question: string;
  asked_by: string;
  asked_at: string;
  status: "open" | "answered" | "cancelled";
  answer: string | null;
  answered_by: string | null;
  answered_at: string | null;
  can_answer?: boolean;
  /** A file the answer came with, kept as the task's evidence. */
  attachment?: { name: string; url: string } | null;
  reminded_at?: string | null;
  escalated_at?: string | null;
}

/** An open question addressed to the viewer, with just the rows it is about. */
export interface QuestionForMe extends InfoRequest {
  subject: string;
  task_label: string;
  group_label: string | null;
  columns: string[];
  rows: Record<string, unknown>[];
}

export interface TaskMessage {
  message_id?: string;
  role: "user" | "assistant";
  author: string;
  text: string;
  meta: { model?: string | null; tool_calls?: string[]; unverified_figures?: number[] };
  created_at?: string;
}

export interface HistoryEntry {
  checkpoint_id: string;
  at: string;
  ended_at?: string;
  source: string;
  event: "start" | "step" | "people" | "waiting" | "end";
  step: string;
  next: string[];
  items: number;
  groups: number;
  findings: number;
}

/** A report the task's publish step wrote (e.g. a PDF), served by the API. */
export interface PublishedDocument {
  name: string;
  tool: string;
  pages: number | null;
  bytes: number | null;
  sha256: string | null;
  written_at: string;
  url: string;
}

export interface InboxRow {
  task_id: string;
  agent_id: string;
  agent_name: string;
  task_label: string;
  subject: string;
  status: TaskStatus;
  team_group: string | null;
  opened_at: string;
  opened_by: string;
  groups: number;
  proposed: number;
  escalated: number;
  decided: number;
  action: "review" | "release" | "gate";
  gate?: string | null;            // waiting at the tollgate before this step
  age_hours?: number;
  due_at?: string | null;
  due_state?: DueState;
  exposure?: number | null;
  unit?: string | null;
  needs_confirmation?: number;
  judgement_calls?: number;
  acting_for?: string | null;
  /** Late items for a key already worked: the day's task. */
  follow_up_of?: string | null;
}

export interface Overview {
  awaiting_my_review: number;
  awaiting_my_release: number;
  open_tasks: number;
  escalated_groups: number;
  tool_calls_24h: number;
  refused_calls_24h: number;
  model_calls_24h: number;
  llm_cost_usd: number;
  llm_groups: number;
  hours_saved_30d?: { value: number; basis: string };
  measured_review?: { decisions: number; median_seconds: number | null; hours_saved: number | null; basis: string };
  agents: { id: string; name: string; task_label: string; statuses: Record<string, number>; escalated_groups: number }[];
}

export interface AuditEvent {
  kind: "tool_call" | "decision" | "release";
  at: string;
  task_id: string;
  subject: string;
  agent_id: string;
  actor: string;
  requested_by?: string;
  tool?: string;
  allowed?: boolean;
  action?: string;
  group_id?: string;
  detail?: string | null;
  row_count?: number | null;
  latency_ms?: number | null;
}

export interface Platform {
  steps: { name: string; label: string; gate: boolean; needs: string[]; produces: string[] }[];
  connectors: {
    id: string;
    name: string;
    transport: string;
    classification: string;
    tools: { name: string; description: string; access: "read" | "write"; scope: { arg: string; key: string }[] | null }[];
  }[];
  llm: string;
  entitlement: string;
}

const enc = encodeURIComponent;

export const useMe = (user: string | null) =>
  useQuery({ queryKey: ["me", user], queryFn: () => api.get<Me>("/me"), enabled: !!user });
export const useDevUsers = () =>
  useQuery({ queryKey: ["dev-users"], queryFn: () => api.get<DevUser[]>("/dev/users") });
export const useOverview = () =>
  useQuery({ queryKey: ["overview"], queryFn: () => api.get<Overview>("/overview") });
export const useInbox = () =>
  useQuery({ queryKey: ["inbox"], queryFn: () => api.get<InboxRow[]>("/inbox") });
export const useAgents = () =>
  useQuery({ queryKey: ["agents"], queryFn: () => api.get<AgentSummary[]>("/agents") });
export const useAgent = (id: string) =>
  useQuery({ queryKey: ["agent", id], queryFn: () => api.get<AgentDetail>(`/agents/${enc(id)}`) });
export const useTasks = (id: string, teamGroup?: string) =>
  useQuery({
    queryKey: ["tasks", id, teamGroup ?? "all"],
    queryFn: () =>
      api.get<TaskSummary[]>(`/agents/${enc(id)}/tasks${teamGroup ? `?team_group=${enc(teamGroup)}` : ""}`),
  });
export const useGroups = (id: string, enabled = true) =>
  useQuery({ queryKey: ["groups", id], queryFn: () => api.get<TeamGroup[]>(`/agents/${enc(id)}/groups`), enabled });
export const useGroup = (id: string, group: string) =>
  useQuery({
    queryKey: ["group", id, group],
    queryFn: () => api.get<TeamGroupDetail>(`/agents/${enc(id)}/groups/${enc(group)}`),
  });
/** A task; while its run is in progress the view polls until it pauses or ends. */
export const useTask = (taskId: string) =>
  useQuery({
    queryKey: ["task", taskId],
    queryFn: () => api.get<TaskDetail>(`/tasks/${enc(taskId)}`),
    refetchInterval: (q) => (q.state.data?.status === "running" ? 1500 : false),
  });
/** A task's Summary tab; `version` changes when its decisions do, so the counts follow. */
export const useTaskSummary = (taskId: string, version: string) =>
  useQuery({ queryKey: ["task-summary", taskId, version], queryFn: () => api.get<TaskSummaryView>(`/tasks/${enc(taskId)}/summary`) });
export const useMessages = (taskId: string) =>
  useQuery({ queryKey: ["messages", taskId], queryFn: () => api.get<TaskMessage[]>(`/tasks/${enc(taskId)}/messages`) });
export const useHistory = (taskId: string, enabled = true) =>
  useQuery({ queryKey: ["history", taskId], queryFn: () => api.get<HistoryEntry[]>(`/tasks/${enc(taskId)}/history`), enabled });
export const useAudit = (agentId?: string) =>
  useQuery({
    queryKey: ["audit", agentId ?? "all"],
    queryFn: () => api.get<AuditEvent[]>(`/audit${agentId ? `?agent_id=${enc(agentId)}` : ""}`),
  });
export const usePlatform = () =>
  useQuery({ queryKey: ["platform"], queryFn: () => api.get<Platform>("/platform") });

/** After anything that moves a task, refresh every view that summarises tasks. */
function useRefreshTasks() {
  const qc = useQueryClient();
  return (detail?: TaskDetail) => {
    if (detail) qc.setQueryData(["task", detail.task_id], detail);
    for (const key of ["inbox", "overview", "audit", "tasks"]) qc.invalidateQueries({ queryKey: [key] });
  };
}

export function useOpenTask(agentId: string) {
  const refresh = useRefreshTasks();
  return useMutation({
    mutationFn: (v: { taskKey: Record<string, string>; teamGroup?: string | null }) =>
      api.post<TaskDetail>(`/agents/${enc(agentId)}/tasks`, {
        task_key: v.taskKey,
        team_group: v.teamGroup ?? null,
      }),
    onSuccess: (detail) => refresh(detail),
  });
}

export function useDecide(taskId: string) {
  const refresh = useRefreshTasks();
  return useMutation({
    mutationFn: (v: {
      groupId: string;
      action: "approve" | "reject";
      comment: string;
      confirmed?: boolean;
      reviewSeconds?: number;
      checklist?: ChecklistAnswer[];
    }) =>
      api.post<{ task: TaskDetail }>(`/tasks/${enc(taskId)}/decisions`, {
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

export function useRelease(taskId: string) {
  const refresh = useRefreshTasks();
  return useMutation({
    mutationFn: () =>
      api.post<{ task: TaskDetail }>(`/tasks/${enc(taskId)}/publish`, { idempotency_key: newIdempotencyKey() }),
    onSuccess: (res) => refresh(res.task),
  });
}

/** Ask a desk, a trader or Operations for evidence about a group or the task. */
export function useAskForEvidence(taskId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { target: string; question: string; group_id: string | null }) =>
      api.post<InfoRequest>(`/tasks/${enc(taskId)}/requests`, v),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["task", taskId] }),
  });
}

export function useCancelRequest(taskId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (requestId: string) => api.post<InfoRequest>(`/requests/${enc(requestId)}/cancel`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["task", taskId] }),
  });
}

export const useMyQuestions = () =>
  useQuery({ queryKey: ["my-questions"], queryFn: () => api.get<QuestionForMe[]>("/requests") });

export function useAnswerQuestion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { requestId: string; answer: string; file?: File | null }) => {
      if (!v.file) return api.post<InfoRequest>(`/requests/${enc(v.requestId)}/answer`, { answer: v.answer });
      const form = new FormData();
      form.append("answer", v.answer);
      form.append("file", v.file);
      return upload<InfoRequest>(`/requests/${enc(v.requestId)}/answer-with-file`, form);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["my-questions"] }),
  });
}

/** A person at a tollgate: continue the run, or stop it with a reason. */
export function usePassGate(taskId: string) {
  const refresh = useRefreshTasks();
  return useMutation({
    mutationFn: (v: { step: string; action: "continue" | "stop"; comment: string | null }) =>
      api.post<TaskDetail>(`/tasks/${enc(taskId)}/gates/${enc(v.step)}`, {
        action: v.action, comment: v.comment, idempotency_key: newIdempotencyKey(),
      }),
    onSuccess: (detail) => refresh(detail),
  });
}

/** Deliver the event a task waits for, by hand (a person the `await` step names). */
export function useDeliverEvent(taskId: string) {
  const refresh = useRefreshTasks();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { step: string; payload: Record<string, unknown> }) =>
      api.post<{ status: string }>(`/tasks/${enc(taskId)}/events/${enc(v.step)}`, { payload: v.payload }),
    onSuccess: () => {
      refresh();
      qc.invalidateQueries({ queryKey: ["task", taskId] });
    },
  });
}

export function useBulkDecide(taskId: string) {
  const refresh = useRefreshTasks();
  return useMutation({
    mutationFn: (v: { groupIds: string[]; action: "approve" | "reject"; comment: string; reviewSeconds?: number }) =>
      api.post<{ task: TaskDetail; decided: { group_id: string }[]; refused: { group_id: string; reason: string }[] }>(
        `/tasks/${enc(taskId)}/decisions/bulk`,
        {
          group_ids: v.groupIds,
          action: v.action,
          comment: v.comment || null,
          review_seconds: v.reviewSeconds ?? null,
          idempotency_key: newIdempotencyKey(),
        },
      ),
    onSuccess: (res) => refresh(res.task),
  });
}

export function useReinvestigate(taskId: string) {
  const refresh = useRefreshTasks();
  return useMutation({
    mutationFn: (v: { groupId: string; note: string }) =>
      api.post<{ task: TaskDetail }>(`/tasks/${enc(taskId)}/groups/${enc(v.groupId)}/reinvestigate`, {
        note: v.note,
        idempotency_key: newIdempotencyKey(),
      }),
    onSuccess: (res) => refresh(res.task),
  });
}

export function useRerun(taskId: string) {
  const refresh = useRefreshTasks();
  return useMutation({
    mutationFn: () => api.post<TaskDetail>(`/tasks/${enc(taskId)}/rerun`, {}),
    onSuccess: (detail) => refresh(detail),
  });
}

export function useRetryPublish(taskId: string) {
  const refresh = useRefreshTasks();
  return useMutation({
    mutationFn: () => api.post<{ task: TaskDetail }>(`/tasks/${enc(taskId)}/publish/retry`, {}),
    onSuccess: (res) => refresh(res.task),
  });
}

export function useLegalHold(taskId: string) {
  const refresh = useRefreshTasks();
  return useMutation({
    mutationFn: (v: { hold: boolean; reason?: string }) =>
      api.post<TaskDetail>(`/tasks/${enc(taskId)}/legal-hold`, { hold: v.hold, reason: v.reason ?? null }),
    onSuccess: (detail) => refresh(detail),
  });
}

export function useAsk(taskId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (question: string) =>
      api.post<{ answer: TaskMessage; messages: TaskMessage[] }>(`/tasks/${enc(taskId)}/ask`, { question }),
    onSuccess: (res) => qc.setQueryData(["messages", taskId], res.messages),
  });
}

// ---------- authoring (BRD → draft manifest) ----------

export interface DraftResult {
  yaml: string;
  manifest: Manifest | null;
  problems: string[];
  assumptions: string[];
  author?: string;
}

export interface PendingDraft {
  agent_id: string;
  version: number;
  name: string;
  note: string;
  drafted_by: string;
  drafted_at: string;
  new: boolean;
  can_approve: boolean;
}

export const useDrafts = () =>
  useQuery({ queryKey: ["drafts"], queryFn: () => api.get<PendingDraft[]>("/authoring/drafts") });

export interface AuthoringModes { guided: boolean; templates: boolean; brd_model: boolean; brd_author: string; brd_note: string | null }
export const useAuthoringModes = () =>
  useQuery({ queryKey: ["authoring-modes"], queryFn: () => api.get<AuthoringModes>("/authoring/modes") });
export const useGuidedDraft = () =>
  useMutation({ mutationFn: (answers: Record<string, unknown>) => api.post<DraftResult>("/authoring/guided", answers) });

export const useDraftFromBrd = () =>
  useMutation({ mutationFn: (brd: string) => api.post<DraftResult>("/authoring/draft", { brd }) });

export function useSubmitDraft() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { yaml: string; note: string }) =>
      api.post<{ agent_id: string; version: number }>("/authoring/submit", v),
    onSuccess: () => {
      for (const key of ["drafts", "agent"]) qc.invalidateQueries({ queryKey: [key] });
    },
  });
}

export function useApproveVersion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { agentId: string; version: number }) =>
      api.post<{ version: number }>(`/agents/${enc(v.agentId)}/versions/${v.version}/approve`, {}),
    onSuccess: () => {
      for (const key of ["drafts", "agents", "agent", "overview"]) qc.invalidateQueries({ queryKey: [key] });
    },
  });
}

/** What a draft would be refused for, checked without storing anything. */
export interface ConfigCheck {
  ok: boolean;
  problems: string[];
}

export function useConfigCheck(agentId: string, body: { manifest?: unknown; config?: unknown } | null) {
  const key = body ? JSON.stringify(body) : "";
  return useQuery({
    queryKey: ["config-check", agentId, key],
    queryFn: () => api.post<ConfigCheck>(`/agents/${enc(agentId)}/check`, body),
    enabled: !!body,
    staleTime: 60_000,
    retry: false,
  });
}

// ---------- team groups ----------

export function useDraftGroup(agentId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { config: GroupConfig; note: string }) =>
      api.post<{ group_id: string; version: number }>(`/agents/${enc(agentId)}/groups`, v),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["group"] }),
  });
}

export function useApproveGroup(agentId: string, group: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (version: number) =>
      api.post<{ version: number }>(`/agents/${enc(agentId)}/groups/${enc(group)}/versions/${version}/approve`, {}),
    onSuccess: () => {
      for (const key of ["group", "groups", "agents"]) qc.invalidateQueries({ queryKey: [key] });
    },
  });
}

// ---------- notifications ----------

export interface NotificationItem {
  notification_id: string;
  kind: string;
  title: string;
  body: string;
  task_id: string | null;
  agent_id: string;
  created_at: string;
  read: boolean;
}

export const useNotifications = (enabled = true) =>
  useQuery({
    queryKey: ["notifications"],
    queryFn: () => api.get<{ unread: number; items: NotificationItem[] }>("/notifications"),
    refetchInterval: 30_000,
    enabled,
  });

export function useMarkRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ids: string[] | null) => api.post<{ marked: number }>("/notifications/read", { ids }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });
}

// ---------- run-the-bank: schedules, switches ----------

export interface Schedule {
  agent_id: string;
  team_group: string | null;
  schedule: string;
  next_run: string | null;
  opens_as: string | null;
  keys: Record<string, string>[];
  timezone: string;
}

export interface SwitchRow {
  kind: "agent" | "group" | "connector";
  target: string;
  off: boolean;
  reason: string;
  set_by: string;
  set_at: string;
  can_switch: boolean;
  history: { off: boolean; reason: string; by: string; at: string }[];
}

export const useSchedules = () => useQuery({ queryKey: ["schedules"], queryFn: () => api.get<Schedule[]>("/schedules") });
export const useSwitches = () => useQuery({ queryKey: ["switches"], queryFn: () => api.get<SwitchRow[]>("/switches") });

export function useSetSwitch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { kind: string; target: string; off: boolean; reason: string }) => api.post("/switches", v),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["switches"] }),
  });
}

// ---------- evidence ----------

export interface Evidence {
  name: string;
  bytes: number;
  sha256: string;
  uploaded_by: string;
  note: string | null;
  uploaded_at: string;
  url: string;
}

export function useUploadEvidence(taskId: string) {
  const refresh = useRefreshTasks();
  return useMutation({
    mutationFn: async (v: { file: File; note: string }) => {
      const form = new FormData();
      form.append("file", v.file);
      if (v.note) form.append("note", v.note);
      return upload<{ task: TaskDetail }>(`/tasks/${enc(taskId)}/evidence`, form);
    },
    onSuccess: (res) => refresh(res.task),
  });
}

// ---------- evals ----------

export interface EvalSummary {
  tasks: number;
  groups_compared: number;
  agree: number;
  disagree: number;
  escalated: number;
  missing: number;
  new: number;
  agreement_rate: number | null;
  verdict_match_rate: number | null;
  wording_mean: number | null;
  cost_usd: number;
}

export interface EvalRunRow {
  run_id: string;
  agent_id: string;
  version: number;
  team_group: string | null;
  group_version: number | null;
  status: "running" | "done" | "failed";
  started_by: string;
  started_at: string;
  finished_at: string | null;
  summary: EvalSummary;
  error: string | null;
}

export const useEvals = (id: string) =>
  useQuery({
    queryKey: ["evals", id],
    queryFn: () => api.get<EvalRunRow[]>(`/agents/${enc(id)}/evals`),
    refetchInterval: (q) => (q.state.data?.some((r) => r.status === "running") ? 2000 : false),
  });

/** How many past settled tasks an eval would replay. */
export const useEvalAvailable = (id: string, teamGroup: string | null) =>
  useQuery({
    queryKey: ["evals-available", id, teamGroup ?? ""],
    queryFn: () => api.get<{ tasks: number; limit: number }>(`/agents/${enc(id)}/evals/available${teamGroup ? `?team_group=${enc(teamGroup)}` : ""}`),
    retry: false,
  });

export interface EvalGroupRow {
  group: string;
  outcome: "agree" | "disagree" | "escalated" | "missing" | "new";
  verdict_match?: boolean | null;
  wording?: number | null;
  expected?: { label: string; action: string; words: string; verdict: string | null; decided_by: string };
  now?: { status?: string; comment?: string; reason?: string; verdict?: string | null };
}

/** One eval run with what each replayed task produced. */
export const useEvalRun = (runId: string | null) =>
  useQuery({
    queryKey: ["eval", runId],
    queryFn: () => api.get<EvalRunRow & { results: { task_id: string; groups: EvalGroupRow[] }[] | null }>(`/evals/${enc(runId!)}`),
    enabled: !!runId,
  });

export function useStartEval(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { version?: number; team_group?: string | null; group_version?: number; limit?: number }) =>
      api.post<EvalRunRow>(`/agents/${enc(id)}/evals`, v),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["evals", id] }),
  });
}

// ---------- developer tools ----------

export interface FlowNode {
  id: string;
  type?: string;
  label?: string | null;
  gate: boolean;
  pause: boolean;
  tools: string[];
  notes: string[];
  people: string[];
}

export interface Flow {
  agent_id: string;
  name: string;
  nodes: FlowNode[];
  edges: { from: string; to: string }[];
  opens: { on: string; schedule: string | null; events: boolean };
}

export interface Template {
  id: string;
  name: string;
  description: string;
  yaml: string;
}

export const useFlow = (id: string, teamGroup?: string | null) =>
  useQuery({
    queryKey: ["flow", id, teamGroup ?? ""],
    queryFn: () => api.get<Flow>(`/agents/${enc(id)}/flow${teamGroup ? `?team_group=${enc(teamGroup)}` : ""}`),
  });

export const useDiff = (id: string, a: number | null, b: number | null, group?: string | null) =>
  useQuery({
    queryKey: ["diff", id, group ?? "", a, b],
    queryFn: () =>
      api.get<{ diff: string; changed: string[] }>(
        group
          ? `/agents/${enc(id)}/groups/${enc(group)}/versions/${a}/diff/${b}`
          : `/agents/${enc(id)}/versions/${a}/diff/${b}`,
      ),
    enabled: a != null && b != null && a !== b,
  });

export const useTemplates = () => useQuery({ queryKey: ["templates"], queryFn: () => api.get<Template[]>("/authoring/templates") });

export function useImportBundle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (bundle: unknown) => api.post<{ agent_id: string; version: number; note: string }>("/promotion/import", { bundle }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["drafts"] }),
  });
}

// ---------- recurring items, delegation ----------

export interface RecurringRow {
  item_id: string;
  team_group: string | null;
  same: Record<string, string>;
  runs: number;
  latest_task_id: string;
  latest_subject: string;
}

export const useRecurring = (id: string, teamGroup?: string, enabled = true) =>
  useQuery({
    queryKey: ["recurring", id, teamGroup ?? "all"],
    queryFn: () =>
      api.get<RecurringRow[]>(`/agents/${enc(id)}/recurring${teamGroup ? `?team_group=${enc(teamGroup)}` : ""}`),
    enabled,
  });

/** The data a configuration reads, and the parameters still to confirm. */
export interface DataContract {
  source: string;
  enrich: string[];
  data: { field: string; used_by: string[]; from: string; derived: boolean }[];
  parameters: { name: string; value: unknown; unit: string | null; used_by: string[]; to_confirm: boolean; missing?: boolean }[];
  to_confirm: string[];
}

export const useDataContract = (id: string, teamGroup?: string) =>
  useQuery({
    queryKey: ["contract", id, teamGroup ?? "all"],
    queryFn: () => api.get<DataContract>(`/agents/${enc(id)}/contract${teamGroup ? `?team_group=${enc(teamGroup)}` : ""}`),
  });

/** What nothing explained, and model-proposed groups reviewers keep approving unchanged. */
export interface Learning {
  unexplained: { task_id: string; subject: string; team_group: string | null; item_id: string; group: string; why: string; amount: number | null; opened_at: string }[];
  unexplained_by_reason: { why: string; items: number }[];
  automation: { team_group: string | null; group_key: Record<string, string>; label: string; verdict: string | null; approved: number; rejected: number; needed: number; tasks: string[] }[];
  /** Conditions on the data that predict the verdict people approved: proposals for the playbook's owners. */
  proposed_checks?: { team_group: string | null; category: string; verdict: string; when: string; covers: number; of: number; wrong: number; precision: number; tasks: string[] }[];
}

export const useLearning = (id: string, teamGroup?: string) =>
  useQuery({
    queryKey: ["learning", id, teamGroup ?? "all"],
    queryFn: () => api.get<Learning>(`/agents/${enc(id)}/learning${teamGroup ? `?team_group=${enc(teamGroup)}` : ""}`),
  });

export interface DelegationRow {
  delegation_id: string;
  from_user: string;
  to_user: string;
  starts_at: string;
  until: string;
  reason: string | null;
  active: boolean;
}

export const useDelegations = () =>
  useQuery({
    queryKey: ["delegations"],
    queryFn: () => api.get<{ away: DelegationRow[]; covering: DelegationRow[] }>("/me/delegations"),
  });

export function useDelegate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { toUser: string; until: string; reason: string }) =>
      api.post<DelegationRow>("/me/delegations", { to_user: v.toUser, until: v.until, reason: v.reason || null }),
    onSuccess: () => {
      for (const key of ["delegations", "inbox", "me"]) qc.invalidateQueries({ queryKey: [key] });
    },
  });
}

export function useEndDelegation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.del(`/me/delegations/${enc(id)}`),
    onSuccess: () => {
      for (const key of ["delegations", "inbox", "me"]) qc.invalidateQueries({ queryKey: [key] });
    },
  });
}
