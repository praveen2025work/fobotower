// Types and TanStack Query hooks for the Helix API (apps/backend/helix/web/main.py).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, newIdempotencyKey } from "./client";

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
}

export interface Finding {
  status: "proposed" | "escalated";
  decided_by: string;
  comment: string;
  reason?: string | null;
  rule?: string;
  model?: string | null;
  usage?: { cost_usd?: number | null; turns?: number | null; input_tokens?: number | null; output_tokens?: number | null };
}

export interface Group {
  group_id: string;
  label: string;
  group_key: Record<string, string>;
  item_ids: string[];
  priors: { comment: string; case_id: string; decided_by: string; at: string }[];
  finding: Finding | null;
  decision: { action: "approve" | "reject"; comment: string | null; decided_by: string; decided_at: string } | null;
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
  can_decide: boolean;
  publish: { tool: string; approver_roles: string[]; can_release: boolean } | null;
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
export const useCase = (caseId: string) =>
  useQuery({ queryKey: ["case", caseId], queryFn: () => api.get<CaseDetail>(`/cases/${enc(caseId)}`) });
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
    mutationFn: (v: { groupId: string; action: "approve" | "reject"; comment: string }) =>
      api.post<{ case: CaseDetail }>(`/cases/${enc(caseId)}/decisions`, {
        group_id: v.groupId,
        action: v.action,
        comment: v.comment || null,
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
    onSuccess: () => qc.invalidateQueries({ queryKey: ["drafts"] }),
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
