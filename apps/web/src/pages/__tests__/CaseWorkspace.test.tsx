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
    const evidence = screen.getByText(/Evidence \(2 connector calls\)/).parentElement!;
    expect(within(evidence).getByText("gl.balances")).toBeInTheDocument();          // case-wide load
    expect(within(evidence).queryByText(/refused/)).not.toBeInTheDocument();        // 7200's refusal is not 6100's
  });

  it("shows why a group was escalated", async () => {
    mockApi({ "GET /cases/fin.c1": detail() });
    open();
    await userEvent.click(await screen.findByRole("button", { name: /account 7200/ }));
    expect(screen.getByText(/Escalated: UNGROUNDED_FIGURE: 4,444.00/)).toBeInTheDocument();
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
    expect(screen.getByText(/— Payroll accrual/)).toBeInTheDocument();
  });

  it("offers release only to someone allowed to release, and says who it waits for", async () => {
    mockApi({ "GET /cases/fin.c1": detail({ status: "awaiting_publish", can_decide: false }) });
    open();
    expect(await screen.findByText(/Waiting for a second person/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Release write-back/ })).not.toBeInTheDocument();
  });

  it("releases the write-back", async () => {
    const calls = mockApi({
      "GET /cases/fin.c1": detail({ status: "awaiting_publish", can_decide: false, publish: { tool: "reporting.publish_commentary", approver_roles: ["FIN_REVIEWER"], can_release: true } }),
      "POST /cases/fin.c1/publish": { case: detail({ status: "completed", outcome: "published", can_decide: false }) },
    });
    open();
    await userEvent.click(await screen.findByRole("button", { name: /Release write-back/ }));
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

  it("shows the server's refusal", async () => {
    mockApi({});
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent("not mocked");
  });
});
