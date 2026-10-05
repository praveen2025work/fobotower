// Types and TanStack Query hooks for the Helix API (apps/backend/helix/web/main.py).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, newIdempotencyKey, upload } from "./client";

export type CaseStatus =
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

export interface CapabilitySummary {
  id: string;
  name: string;
  description: string;
  version: number;
  case_label: string;
  item_label: string;
  case_key: string[];
  steps: string[];
  is_owner: boolean;
  can_decide: boolean;
  configurable: string[];
  groups: { group: string; name: string }[];
}

/** A team group: one team's configuration of a capability (e.g. a rec group). */
export interface TeamGroup {
  capability_id: string;
  group: string;
  name: string;
  description: string;
  version: number;
  owners: { people: string[]; role: string | null; four_eyes: boolean };
  sets: string[];
  case_label: string;
  item_label: string;
  case_key: string[];
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
  versions: (CapabilityVersion & { config: GroupConfig })[];
}

export interface Manifest {
  id: string;
  name: string;
  description: string;
  owners: { people: string[]; role: string | null; four_eyes: boolean };
  case: { label: string; item_label: string; key: string[]; subject: string | null; scopes: Record<string, string>; opens_on: string };
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

export interface CapabilityVersion {
  version: number;
  status: string;
  note: string;
  drafted_by: string;
  drafted_at: string;
  decided_by: string | null;
  decided_at: string | null;
}

export interface CapabilityDetail {
  version: number;
  manifest: Manifest;
  versions: CapabilityVersion[];
}

export interface CaseSummary {
  case_id: string;
  capability_id: string;
  subject: string;
  case_key: Record<string, string>;
  status: CaseStatus;
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

/** Why a group needs more than a click (helix/review.py). */
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
  // playbook capabilities (e.g. FOBO): what the playbook says about the group
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
}

export interface Group {
  group_id: string;
  label: string;
  group_key: Record<string, string>;
  item_ids: string[];
  priors: { comment: string; case_id: string; decided_by: string; at: string; match?: string }[];
  finding: Finding | null;
  decision: {
    action: "approve" | "reject";
    comment: string | null;
    decided_by: string;
    decided_at: string;
    on_behalf_of?: string | null;
    confirmed?: boolean;
  } | null;
  flags?: ReviewFlag[];
  /** Flags that keep this group out of "Approve all" (review.bulk_exclude). */
  bulk_blockers?: ReviewFlag[];
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

export interface CaseDetail extends CaseSummary {
  draft: { headline: string } | null;
  labels: { case: string; item: string };
  steps: string[];
  pause_before: string[];
  columns: string[];
  items: ({ item_id: string; in_scope: boolean } & Record<string, unknown>)[];
  groups: Group[];
  decisions: { group_id: string; action: string; comment: string | null; decided_by: string; decided_at: string }[];
  tool_calls: ToolCall[];
  documents: PublishedDocument[];
  evidence?: Evidence[];
  attempts: { case_id: string; attempt: number; status: CaseStatus; outcome: string | null; opened_by: string; opened_at: string }[];
  can_decide: boolean;
  /** Deciding on behalf of this absent colleague (delegation). */
  acting_for?: string | null;
  due_state?: DueState;
  exposure?: number | null;
  unit?: string | null;
  id_field?: string;
  amount_field?: string | null;
  /** item_id -> how often it has come back (insights.recurring). */
  recurring?: Record<string, { runs: number; earlier: { case_id: string; subject: string; opened_at: string }[] }>;
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
  };
  publish: {
    tool: string;
    approver_roles: string[];
    can_release: boolean;
    per?: "group" | "case";
    released?: { by: string; at: string } | null;
  } | null;
  /** Who the case waits on; when it is not the viewer, why not. */
  waiting_on?: {
    step: "review" | "release";
    roles: string[];
    you: boolean;
    why_not: string | null;
    reviewed_by?: string[];
  } | null;
}

export interface CaseMessage {
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

/** A report the case's publish step wrote (e.g. a PDF), served by the API. */
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
  case_id: string;
  capability_id: string;
  capability_name: string;
  case_label: string;
  subject: string;
  status: CaseStatus;
  team_group: string | null;
  opened_at: string;
  opened_by: string;
  groups: number;
  proposed: number;
  escalated: number;
  decided: number;
  action: "review" | "release";
  age_hours?: number;
  due_at?: string | null;
  due_state?: DueState;
  exposure?: number | null;
  unit?: string | null;
  needs_confirmation?: number;
  judgement_calls?: number;
  acting_for?: string | null;
}

export interface Overview {
  awaiting_my_review: number;
  awaiting_my_release: number;
  open_cases: number;
  escalated_groups: number;
  tool_calls_24h: number;
  refused_calls_24h: number;
  model_calls_24h: number;
  llm_cost_usd: number;
  llm_groups: number;
  hours_saved_30d?: { value: number; basis: string };
  measured_review?: { decisions: number; median_seconds: number | null; hours_saved: number | null; basis: string };
  capabilities: { id: string; name: string; case_label: string; statuses: Record<string, number>; escalated_groups: number }[];
}

export interface AuditEvent {
  kind: "tool_call" | "decision" | "release";
  at: string;
  case_id: string;
  subject: string;
  capability_id: string;
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
    tools: { name: string; description: string; access: "read" | "write"; scope: { arg: string; key: string } | null }[];
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
export const useCapabilities = () =>
  useQuery({ queryKey: ["capabilities"], queryFn: () => api.get<CapabilitySummary[]>("/capabilities") });
export const useCapability = (id: string) =>
  useQuery({ queryKey: ["capability", id], queryFn: () => api.get<CapabilityDetail>(`/capabilities/${enc(id)}`) });
export const useCases = (id: string, teamGroup?: string) =>
  useQuery({
    queryKey: ["cases", id, teamGroup ?? "all"],
    queryFn: () =>
      api.get<CaseSummary[]>(`/capabilities/${enc(id)}/cases${teamGroup ? `?team_group=${enc(teamGroup)}` : ""}`),
  });
export const useGroups = (id: string, enabled = true) =>
  useQuery({ queryKey: ["groups", id], queryFn: () => api.get<TeamGroup[]>(`/capabilities/${enc(id)}/groups`), enabled });
export const useGroup = (id: string, group: string) =>
  useQuery({
    queryKey: ["group", id, group],
    queryFn: () => api.get<TeamGroupDetail>(`/capabilities/${enc(id)}/groups/${enc(group)}`),
  });
/** A case; while its run is in progress the view polls until it pauses or ends. */
export const useCase = (caseId: string) =>
  useQuery({
    queryKey: ["case", caseId],
    queryFn: () => api.get<CaseDetail>(`/cases/${enc(caseId)}`),
    refetchInterval: (q) => (q.state.data?.status === "running" ? 1500 : false),
  });
export const useMessages = (caseId: string) =>
  useQuery({ queryKey: ["messages", caseId], queryFn: () => api.get<CaseMessage[]>(`/cases/${enc(caseId)}/messages`) });
export const useHistory = (caseId: string, enabled = true) =>
  useQuery({ queryKey: ["history", caseId], queryFn: () => api.get<HistoryEntry[]>(`/cases/${enc(caseId)}/history`), enabled });
export const useAudit = (capabilityId?: string) =>
  useQuery({
    queryKey: ["audit", capabilityId ?? "all"],
    queryFn: () => api.get<AuditEvent[]>(`/audit${capabilityId ? `?capability_id=${enc(capabilityId)}` : ""}`),
  });
export const usePlatform = () =>
  useQuery({ queryKey: ["platform"], queryFn: () => api.get<Platform>("/platform") });

/** After anything that moves a case, refresh every view that summarises cases. */
function useRefreshCases() {
  const qc = useQueryClient();
  return (detail?: CaseDetail) => {
    if (detail) qc.setQueryData(["case", detail.case_id], detail);
    for (const key of ["inbox", "overview", "audit", "cases"]) qc.invalidateQueries({ queryKey: [key] });
  };
}

export function useOpenCase(capabilityId: string) {
  const refresh = useRefreshCases();
  return useMutation({
    mutationFn: (v: { caseKey: Record<string, string>; teamGroup?: string | null }) =>
      api.post<CaseDetail>(`/capabilities/${enc(capabilityId)}/cases`, {
        case_key: v.caseKey,
        team_group: v.teamGroup ?? null,
      }),
    onSuccess: (detail) => refresh(detail),
  });
}

export function useDecide(caseId: string) {
  const refresh = useRefreshCases();
  return useMutation({
    mutationFn: (v: {
      groupId: string;
      action: "approve" | "reject";
      comment: string;
      confirmed?: boolean;
      reviewSeconds?: number;
    }) =>
      api.post<{ case: CaseDetail }>(`/cases/${enc(caseId)}/decisions`, {
        group_id: v.groupId,
        action: v.action,
        comment: v.comment || null,
        confirmed: v.confirmed ?? false,
        review_seconds: v.reviewSeconds ?? null,
        idempotency_key: newIdempotencyKey(),
      }),
    onSuccess: (res) => refresh(res.case),
  });
}

export function useRelease(caseId: string) {
  const refresh = useRefreshCases();
  return useMutation({
    mutationFn: () =>
      api.post<{ case: CaseDetail }>(`/cases/${enc(caseId)}/publish`, { idempotency_key: newIdempotencyKey() }),
    onSuccess: (res) => refresh(res.case),
  });
}

export function useBulkDecide(caseId: string) {
  const refresh = useRefreshCases();
  return useMutation({
    mutationFn: (v: { groupIds: string[]; action: "approve" | "reject"; comment: string; reviewSeconds?: number }) =>
      api.post<{ case: CaseDetail; decided: { group_id: string }[]; refused: { group_id: string; reason: string }[] }>(
        `/cases/${enc(caseId)}/decisions/bulk`,
        {
          group_ids: v.groupIds,
          action: v.action,
          comment: v.comment || null,
          review_seconds: v.reviewSeconds ?? null,
          idempotency_key: newIdempotencyKey(),
        },
      ),
    onSuccess: (res) => refresh(res.case),
  });
}

export function useReinvestigate(caseId: string) {
  const refresh = useRefreshCases();
  return useMutation({
    mutationFn: (v: { groupId: string; note: string }) =>
      api.post<{ case: CaseDetail }>(`/cases/${enc(caseId)}/groups/${enc(v.groupId)}/reinvestigate`, {
        note: v.note,
        idempotency_key: newIdempotencyKey(),
      }),
    onSuccess: (res) => refresh(res.case),
  });
}

export function useRerun(caseId: string) {
  const refresh = useRefreshCases();
  return useMutation({
    mutationFn: () => api.post<CaseDetail>(`/cases/${enc(caseId)}/rerun`, {}),
    onSuccess: (detail) => refresh(detail),
  });
}

export function useRetryPublish(caseId: string) {
  const refresh = useRefreshCases();
  return useMutation({
    mutationFn: () => api.post<{ case: CaseDetail }>(`/cases/${enc(caseId)}/publish/retry`, {}),
    onSuccess: (res) => refresh(res.case),
  });
}

export function useLegalHold(caseId: string) {
  const refresh = useRefreshCases();
  return useMutation({
    mutationFn: (v: { hold: boolean; reason?: string }) =>
      api.post<CaseDetail>(`/cases/${enc(caseId)}/legal-hold`, { hold: v.hold, reason: v.reason ?? null }),
    onSuccess: (detail) => refresh(detail),
  });
}

export function useAsk(caseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (question: string) =>
      api.post<{ answer: CaseMessage; messages: CaseMessage[] }>(`/cases/${enc(caseId)}/ask`, { question }),
    onSuccess: (res) => qc.setQueryData(["messages", caseId], res.messages),
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
  capability_id: string;
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

export const useDraftFromBrd = () =>
  useMutation({ mutationFn: (brd: string) => api.post<DraftResult>("/authoring/draft", { brd }) });

export function useSubmitDraft() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { yaml: string; note: string }) =>
      api.post<{ capability_id: string; version: number }>("/authoring/submit", v),
    onSuccess: () => {
      for (const key of ["drafts", "capability"]) qc.invalidateQueries({ queryKey: [key] });
    },
  });
}

export function useApproveVersion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { capabilityId: string; version: number }) =>
      api.post<{ version: number }>(`/capabilities/${enc(v.capabilityId)}/versions/${v.version}/approve`, {}),
    onSuccess: () => {
      for (const key of ["drafts", "capabilities", "capability", "overview"]) qc.invalidateQueries({ queryKey: [key] });
    },
  });
}

/** What a draft would be refused for, checked without storing anything. */
export interface ConfigCheck {
  ok: boolean;
  problems: string[];
}

export function useConfigCheck(capabilityId: string, body: { manifest?: unknown; config?: unknown } | null) {
  const key = body ? JSON.stringify(body) : "";
  return useQuery({
    queryKey: ["config-check", capabilityId, key],
    queryFn: () => api.post<ConfigCheck>(`/capabilities/${enc(capabilityId)}/check`, body),
    enabled: !!body,
    staleTime: 60_000,
    retry: false,
  });
}

// ---------- team groups ----------

export function useDraftGroup(capabilityId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { config: GroupConfig; note: string }) =>
      api.post<{ group_id: string; version: number }>(`/capabilities/${enc(capabilityId)}/groups`, v),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["group"] }),
  });
}

export function useApproveGroup(capabilityId: string, group: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (version: number) =>
      api.post<{ version: number }>(`/capabilities/${enc(capabilityId)}/groups/${enc(group)}/versions/${version}/approve`, {}),
    onSuccess: () => {
      for (const key of ["group", "groups", "capabilities"]) qc.invalidateQueries({ queryKey: [key] });
    },
  });
}

// ---------- notifications ----------

export interface NotificationItem {
  notification_id: string;
  kind: string;
  title: string;
  body: string;
  case_id: string | null;
  capability_id: string;
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
  capability_id: string;
  team_group: string | null;
  schedule: string;
  next_run: string | null;
  opens_as: string | null;
  keys: Record<string, string>[];
  timezone: string;
}

export interface SwitchRow {
  kind: "capability" | "group" | "connector";
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

export function useUploadEvidence(caseId: string) {
  const refresh = useRefreshCases();
  return useMutation({
    mutationFn: async (v: { file: File; note: string }) => {
      const form = new FormData();
      form.append("file", v.file);
      if (v.note) form.append("note", v.note);
      return upload<{ case: CaseDetail }>(`/cases/${enc(caseId)}/evidence`, form);
    },
    onSuccess: (res) => refresh(res.case),
  });
}

// ---------- evals ----------

export interface EvalSummary {
  cases: number;
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
  capability_id: string;
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
    queryFn: () => api.get<EvalRunRow[]>(`/capabilities/${enc(id)}/evals`),
    refetchInterval: (q) => (q.state.data?.some((r) => r.status === "running") ? 2000 : false),
  });

export function useStartEval(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { version?: number; team_group?: string | null; group_version?: number; limit?: number }) =>
      api.post<EvalRunRow>(`/capabilities/${enc(id)}/evals`, v),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["evals", id] }),
  });
}

// ---------- developer tools ----------

export interface FlowNode {
  id: string;
  gate: boolean;
  pause: boolean;
  tools: string[];
  notes: string[];
  people: string[];
}

export interface Flow {
  capability_id: string;
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
    queryFn: () => api.get<Flow>(`/capabilities/${enc(id)}/flow${teamGroup ? `?team_group=${enc(teamGroup)}` : ""}`),
  });

export const useDiff = (id: string, a: number | null, b: number | null, group?: string | null) =>
  useQuery({
    queryKey: ["diff", id, group ?? "", a, b],
    queryFn: () =>
      api.get<{ diff: string; changed: string[] }>(
        group
          ? `/capabilities/${enc(id)}/groups/${enc(group)}/versions/${a}/diff/${b}`
          : `/capabilities/${enc(id)}/versions/${a}/diff/${b}`,
      ),
    enabled: a != null && b != null && a !== b,
  });

export const useTemplates = () => useQuery({ queryKey: ["templates"], queryFn: () => api.get<Template[]>("/authoring/templates") });

export function useImportBundle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (bundle: unknown) => api.post<{ capability_id: string; version: number; note: string }>("/promotion/import", { bundle }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["drafts"] }),
  });
}

// ---------- recurring items, delegation ----------

export interface RecurringRow {
  item_id: string;
  team_group: string | null;
  same: Record<string, string>;
  runs: number;
  latest_case_id: string;
  latest_subject: string;
}

export const useRecurring = (id: string, teamGroup?: string, enabled = true) =>
  useQuery({
    queryKey: ["recurring", id, teamGroup ?? "all"],
    queryFn: () =>
      api.get<RecurringRow[]>(`/capabilities/${enc(id)}/recurring${teamGroup ? `?team_group=${enc(teamGroup)}` : ""}`),
    enabled,
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
