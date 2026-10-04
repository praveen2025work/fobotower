import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CaseDetail, Group } from "../../api/helix";
import { mockApi, renderAt } from "../../test/render";
import CaseWorkspace from "../CaseWorkspace";

const group = (id: string, extra: Partial<Group> = {}): Group => ({
  group_id: id,
  label: `account ${id}`,
  group_key: { account: id },
  item_ids: [`L-${id}`],
  priors: [],
  finding: { status: "proposed", decided_by: "llm:agent-sdk", comment: `Account ${id} explained.`, model: "claude-opus-5-5", usage: { cost_usd: 0.0123, turns: 3 } },
  decision: null,
  ...extra,
});

const detail = (extra: Partial<CaseDetail> = {}): CaseDetail => ({
  case_id: "fin.c1",
  capability_id: "fin.variance-commentary",
  subject: "UK01 · 2026-09",
  case_key: { entity: "UK01", period: "2026-09" },
  status: "awaiting_review",
  outcome: null,
  manifest_version: 1,
  team_group: null,
  team_group_version: null,
  opened_by: "alice",
  opened_at: "2026-10-03T10:00:00Z",
  trace_id: "abc123",
  error: null,
  draft: { headline: "2 of 14 lines in scope" },
  labels: { case: "Lane", item: "Variance line" },
  steps: ["load", "compare", "group", "reason", "draft", "validate", "review", "record", "publish"],
  pause_before: ["review", "publish"],
  columns: ["account", "variance"],
  items: [
    { item_id: "L-6100", in_scope: true, account: "6100", variance: 66353.03 },
    { item_id: "L-7200", in_scope: true, account: "7200", variance: -98580.15 },
  ],
  groups: [group("6100"), group("7200", { finding: { status: "escalated", decided_by: "llm:agent-sdk", comment: "", reason: "UNGROUNDED_FIGURE: 4,444.00" } })],
  decisions: [],
  tool_calls: [
    { call_id: "t1", tool: "gl.balances", connector_id: "gl", requested_by: "load", caller: "alice", arguments: { entity: "UK01", period: "2026-09" }, allowed: true, denied_reason: null, row_count: 14, error: null, latency_ms: 20, called_at: "" },
    { call_id: "t2", tool: "gl.journal_lines", connector_id: "gl", requested_by: "llm", caller: "alice", arguments: { entity: "UK01", period: "2026-09", account: "6100" }, allowed: true, denied_reason: null, row_count: 4, error: null, latency_ms: 3, called_at: "" },
    { call_id: "t3", tool: "gl.journal_lines", connector_id: "gl", requested_by: "llm", caller: "alice", arguments: { entity: "US01", account: "7200" }, allowed: false, denied_reason: "alice is not entitled to entity=US01", row_count: null, error: null, latency_ms: null, called_at: "" },
  ],
  can_decide: true,
  documents: [],
  attempt: 1,
  rerun_of: null,
  legal_hold: false,
  legal_hold_reason: null,
  attempts: [],
  can_rerun: false,
  can_retry_publish: false,
  can_hold: false,
  review: { require_comment: ["reject", "escalated"], opener_may_decide: true, dual_review_when: null, max_reinvestigations: 2 },
  publish: { tool: "reporting.publish_commentary", approver_roles: ["FIN_REVIEWER"], can_release: false },
  ...extra,
});

afterEach(() => vi.unstubAllGlobals());

const open = () => renderAt("/cases/fin.c1", "/cases/:caseId", <CaseWorkspace />);

describe("CaseWorkspace", () => {
  it("shows the proposal, who reached it, and only this group's evidence", async () => {
    mockApi({ "GET /cases/fin.c1": detail() });
    open();
    expect(await screen.findByText("Account 6100 explained.")).toBeInTheDocument();
    expect(screen.getByText(/claude-opus-5-5 · 3 turns · \$0.0123/)).toBeInTheDocument();
    const evidence = screen.getByText(/Data used \(2 system calls\)/).parentElement!;
    expect(within(evidence).getByText("gl.balances")).toBeInTheDocument();          // case-wide load
    expect(within(evidence).queryByText(/refused/)).not.toBeInTheDocument();        // 7200's refusal is not 6100's
  });

  it("shows why a group was escalated", async () => {
    mockApi({ "GET /cases/fin.c1": detail() });
    open();
    await userEvent.click(await screen.findByRole("button", { name: /account 7200/ }));
    const why = screen.getByRole("region", { name: "Why it was escalated" });
    expect(within(why).getByText(/quoted figures that are not in the data \(4,444.00\)/)).toBeInTheDocument();
    expect(screen.getByText(/refused: alice is not entitled to entity=US01/)).toBeInTheDocument();
  });

  it("records a decision with the reviewer's explanation and an idempotency key", async () => {
    const decided = detail({ groups: [group("6100", { decision: { action: "approve", comment: "Payroll accrual", decided_by: "alice", decided_at: "2026-10-03T11:00:00Z" } }), detail().groups[1]] });
    const calls = mockApi({ "GET /cases/fin.c1": detail(), "POST /cases/fin.c1/decisions": { case: decided } });
    open();
    await userEvent.type(await screen.findByLabelText(/Your explanation/), "Payroll accrual");
    await userEvent.click(screen.getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
    const post = calls.find((c) => c.method === "POST")!.body as Record<string, string>;
    expect(post).toMatchObject({ group_id: "6100", action: "approve", comment: "Payroll accrual" });
    expect(post.idempotency_key.length).toBeGreaterThanOrEqual(8);
    // the list marks 6100 approved and the panel moves on to the next undecided proposal
    const item = await screen.findByRole("button", { name: /account 6100/ });
    expect(await within(item).findByText("approved")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "account 7200" })).toBeInTheDocument();
    await userEvent.click(item);
    expect(screen.getByText("Payroll accrual", { selector: "p" })).toBeInTheDocument();
  });

  it("tells someone who cannot release who will, and why not them", async () => {
    mockApi({
      "GET /cases/fin.c1": detail({
        status: "awaiting_publish",
        can_decide: false,
        publish: { tool: "reporting.publish_commentary", approver_roles: ["FIN_REVIEWER"], can_release: false },
        waiting_on: { step: "release", roles: ["FIN_REVIEWER"], you: false, why_not: "you reviewed this case; a second person who did not review it releases it", reviewed_by: ["bob"] },
      }),
    });
    open();
    const card = await screen.findByRole("status", { name: "Waiting for release" });
    expect(card).toHaveTextContent("You reviewed it, so it can't be you.");
    expect(within(card).queryByRole("button")).not.toBeInTheDocument();
  });

  it("offers release only to someone allowed to release, and says who it waits for", async () => {
    mockApi({ "GET /cases/fin.c1": detail({ status: "awaiting_publish", can_decide: false }) });
    open();
    expect(await screen.findByText(/Waiting for a second person/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Release write-back/ })).not.toBeInTheDocument();
  });

  it("releases the write-back", async () => {
    const calls = mockApi({
      "GET /cases/fin.c1": detail({
        status: "awaiting_publish",
        can_decide: false,
        groups: [group("6100", { decision: { action: "approve", comment: "Payroll accrual", decided_by: "alice", decided_at: "2026-10-03T11:00:00Z" } })],
        publish: { tool: "reporting.publish_commentary", approver_roles: ["FIN_REVIEWER"], can_release: true },
        waiting_on: { step: "release", roles: ["FIN_REVIEWER"], you: true, why_not: null, reviewed_by: ["alice"] },
      }),
      "POST /cases/fin.c1/publish": { case: detail({ status: "completed", outcome: "published", can_decide: false }) },
    });
    open();
    // the release is offered at the top, with what will be written listed before it is
    expect(await screen.findByRole("status", { name: "Ready for your release" })).toHaveTextContent("Reviewed by alice");
    const summary = screen.getByRole("region", { name: "What will be released" });
    expect(within(summary).getByText("Payroll accrual")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Release write-back/ }));
    expect(await screen.findByText("Published.")).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST")!.path).toBe("/cases/fin.c1/publish");
  });

  it("lists the published report and downloads it with the caller's identity", async () => {
    const doc = { name: "rv.c1.pdf", tool: "documents.render_pdf_report", pages: 2, bytes: 2780, sha256: "ab", written_at: "2026-10-04T10:03:00Z", url: "/api/cases/fin.c1/documents/rv.c1.pdf" };
    const calls = mockApi({
      "GET /cases/fin.c1": detail({ status: "completed", outcome: "published", can_decide: false, documents: [doc] }),
      "GET /cases/fin.c1/documents/rv.c1.pdf": {},
    });
    URL.createObjectURL = vi.fn(() => "blob:x");
    URL.revokeObjectURL = vi.fn();
    open();
    await userEvent.click(await screen.findByRole("button", { name: /rv\.c1\.pdf/ }));
    expect(calls.map((c) => c.path)).toContain("/cases/fin.c1/documents/rv.c1.pdf");
    expect(URL.createObjectURL).toHaveBeenCalled();
  });

  it("approving an escalated group needs the reviewer's own words; rejecting always does", async () => {
    mockApi({ "GET /cases/fin.c1": detail() });
    open();
    await userEvent.click(await screen.findByRole("button", { name: /account 7200/ }));
    expect(screen.getByLabelText(/required: this group was escalated/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Reject" })).toBeDisabled();
    await userEvent.type(screen.getByLabelText(/Your explanation/), "Accrual reversal");
    expect(screen.getByRole("button", { name: "Approve" })).toBeEnabled();
  });

  it("approves every proposed group at once and says which need a person", async () => {
    const calls = mockApi({
      "GET /cases/fin.c1": detail({ groups: [group("6100"), group("6200"), detail().groups[1]] }),
      "POST /cases/fin.c1/decisions/bulk": { case: detail(), decided: [{ group_id: "6100" }, { group_id: "6200" }], refused: [] },
    });
    open();
    await userEvent.click(await screen.findByRole("button", { name: /Approve 2 straightforward/ }));
    await waitFor(() => expect(calls.some((c) => c.path === "/cases/fin.c1/decisions/bulk")).toBe(true));
    const body = calls.find((c) => c.path === "/cases/fin.c1/decisions/bulk")!.body as { group_ids: string[] };
    expect(body.group_ids).toEqual(["6100", "6200"]);           // never the escalated 7200
  });

  it("leaves a verdict needing confirmation out of bulk approval and asks for a tick and words", async () => {
    const flagged = group("6300", {
      flags: ["confirmation"],
      bulk_blockers: ["confirmation"],
      finding: { ...group("6300").finding!, verdict: "POST", requires_confirmation: "POST depends on unset policy: materiality_threshold" },
    });
    const calls = mockApi({
      "GET /cases/fin.c1": detail({ groups: [flagged, group("6100"), group("6200")] }),
      "POST /cases/fin.c1/decisions": { case: detail() },
    });
    open();
    expect(await screen.findByRole("button", { name: /Approve 2 straightforward/ })).toBeInTheDocument();
    expect(screen.getByText(/1 needs one-by-one review/)).toBeInTheDocument();
    expect(screen.getAllByText("Needs confirmation").length).toBeGreaterThan(0);
    const approve = screen.getByRole("button", { name: "Approve" });
    expect(approve).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox"));
    expect(approve).toBeDisabled();                               // words are required too
    await userEvent.type(screen.getByLabelText(/Your explanation/), "Materiality agreed with PC");
    await userEvent.click(approve);
    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
    expect(calls.find((c) => c.method === "POST")!.body).toMatchObject({ group_id: "6300", confirmed: true });
  });

  it("sends a group back to the model with the reviewer's note", async () => {
    const calls = mockApi({
      "GET /cases/fin.c1": detail(),
      "POST /cases/fin.c1/groups/6100/reinvestigate": { case: detail(), replayed: false, status: "awaiting_review" },
    });
    open();
    await userEvent.type(await screen.findByLabelText(/Ask the model to look again/), "Check the October reversal");
    await userEvent.click(screen.getByRole("button", { name: /Investigate again/ }));
    await waitFor(() => expect(calls.some((c) => c.path.endsWith("/reinvestigate"))).toBe(true));
    expect(calls.find((c) => c.path.endsWith("/reinvestigate"))!.body).toMatchObject({ note: "Check the October reversal" });
  });

  it("shows a running case and a failed one with its way forward", async () => {
    mockApi({ "GET /cases/fin.c1": detail({ status: "running", groups: [] }) });
    open();
    expect(await screen.findByRole("status")).toHaveTextContent(/Running — this page updates by itself/);
  });

  it("re-runs a failed case as a new attempt", async () => {
    const calls = mockApi({
      "GET /cases/fin.c1": detail({ status: "failed", error: "RuntimeError: GL connector timed out", can_rerun: true, groups: [] }),
      "POST /cases/fin.c1/rerun": detail({ case_id: "fin.c1.r2", attempt: 2 }),
    });
    open();
    expect(await screen.findByText(/The run failed: RuntimeError: GL connector timed out/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Run again/ }));
    await waitFor(() => expect(calls.some((c) => c.path === "/cases/fin.c1/rerun")).toBe(true));
  });

  it("offers a retry when a write-back failed part-way", async () => {
    const calls = mockApi({
      "GET /cases/fin.c1": detail({ status: "failed", outcome: "publish_failed", can_retry_publish: true, can_decide: false }),
      "POST /cases/fin.c1/publish/retry": { case: detail({ status: "completed", outcome: "published", can_decide: false }) },
    });
    open();
    await userEvent.click(await screen.findByRole("button", { name: /Retry write-back/ }));
    expect(await screen.findByText("Published.")).toBeInTheDocument();
    expect(calls.some((c) => c.path === "/cases/fin.c1/publish/retry")).toBe(true);
  });

  it("shows what a playbook concluded: category, side, verdict, owner, checks and confirmation", async () => {
    const fobo = detail({
      columns: ["instrument", "difference"],
      items: [{ item_id: "JGB 10Y", in_scope: true, instrument: "JGB 10Y", difference: 85.5,
                checks: [{ id: "C1", positive: true, reason: "Nostro statement received after 23:30 cutoff" }, { id: "C2", positive: false, reason: "" }] }],
      groups: [{
        group_id: "C-BO", label: "category C, side BO", group_key: { category: "C", side: "BO" }, item_ids: ["JGB 10Y"], priors: [], decision: null,
        finding: { status: "proposed", decided_by: "playbook", comment: "Redemption break (BO): Nostro statement received after 23:30 cutoff.",
                   verdict: "POST", category: "C", category_name: "Redemption break", side: "BO", escalate_to: "CATS support",
                   requires_confirmation: "POST depends on unset policy: materiality_threshold" },
      }],
    });
    mockApi({ "GET /cases/fin.c1": fobo });
    open();
    const play = await screen.findByLabelText("Playbook");
    expect(within(play).getByText("C · Redemption break")).toBeInTheDocument();
    expect(within(play).getByText("POST")).toBeInTheDocument();
    expect(within(play).getByText("CATS support")).toBeInTheDocument();
    expect(within(play).getByText(/Requires controller confirmation/)).toBeInTheDocument();
    expect(screen.getByTitle("C1: Nostro statement received after 23:30 cutoff")).toBeInTheDocument();
    expect(screen.getByTitle("C2: ruled out")).toBeInTheDocument();
  });

  it("answers a question about the case and flags untraceable figures", async () => {
    const calls = mockApi({
      "GET /cases/fin.c1": detail(),
      "GET /cases/fin.c1/messages": [],
      "POST /cases/fin.c1/ask": {
        answer: { role: "assistant", author: "llm:stub", text: "Account 6100 is 1,234.00 off.", meta: { unverified_figures: [1234] } },
        messages: [
          { role: "user", author: "alice", text: "Why 6100?", meta: {} },
          { role: "assistant", author: "llm:stub", text: "Account 6100 is 1,234.00 off.", meta: { unverified_figures: [1234] } },
        ],
      },
    });
    open();
    await userEvent.click(await screen.findByRole("tab", { name: "Ask about this case" }));
    await userEvent.type(screen.getByLabelText("Your question"), "Why 6100?");
    await userEvent.click(screen.getByRole("button", { name: /Ask/ }));
    expect(await screen.findByText("Account 6100 is 1,234.00 off.")).toBeInTheDocument();
    expect(screen.getByText(/Not traceable to this case's data: 1,234/)).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST")!.body).toEqual({ question: "Why 6100?" });
  });

  it("shows the run step by step", async () => {
    mockApi({
      "GET /cases/fin.c1": detail(),
      "GET /cases/fin.c1/history": [
        { checkpoint_id: "a", at: "2026-10-03T10:00:00Z", source: "input", event: "start", step: "start", next: ["load"], items: 0, groups: 0, findings: 0 },
        { checkpoint_id: "b", at: "2026-10-03T10:00:00Z", ended_at: "2026-10-03T10:00:01.5Z", source: "loop", event: "step", step: "load", next: ["load"], items: 0, groups: 0, findings: 0 },
        { checkpoint_id: "c", at: "2026-10-03T10:00:02Z", source: "loop", event: "waiting", step: "review", next: ["review"], items: 14, groups: 2, findings: 2 },
      ],
    });
    open();
    await userEvent.click(await screen.findByRole("tab", { name: "Run history" }));
    const list = await screen.findByRole("list", { name: "Run history" });
    expect(within(list).getByText("load")).toBeInTheDocument();
    expect(within(list).getByText("1.5 s")).toBeInTheDocument();
    expect(within(list).getByText("waiting before review")).toBeInTheDocument();
  });

  it("shows the server's refusal", async () => {
    mockApi({});
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent("not mocked");
  });
});
