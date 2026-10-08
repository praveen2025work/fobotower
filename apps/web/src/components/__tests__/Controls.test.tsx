import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, renderAt } from "../../test/render";
import NotificationBell from "../NotificationBell";
import { SchedulesPanel, SwitchesPanel } from "../ops/ControlsPanel";
import EvidencePanel from "../case/EvidencePanel";
import FlowDiagram from "../capability/FlowDiagram";
import EvalsPanel from "../capability/EvalsPanel";
import VersionsPanel from "../capability/VersionsPanel";
import type { CaseDetail } from "../../api/aof";

afterEach(() => vi.unstubAllGlobals());

describe("notifications", () => {
  it("shows unread notifications and opens the case", async () => {
    const calls = mockApi({
      "GET /notifications": { unread: 1, items: [{ notification_id: "n1", kind: "review_needed", title: "Lane: UK01 · 2026-09 needs your review", body: "3 groups", case_id: "fin.c1", capability_id: "fin", created_at: "2026-10-04T07:00:00Z", read: false }] },
      "POST /notifications/read": { marked: 1 },
    });
    renderAt("/", "/", <NotificationBell />);
    await userEvent.click(await screen.findByRole("button", { name: "Notifications, 1 unread" }));
    await userEvent.click(screen.getByText(/needs your review/));
    await waitFor(() => expect(calls.find((c) => c.method === "POST")?.body).toEqual({ ids: ["n1"] }));
    expect(await screen.findByText("elsewhere")).toBeInTheDocument();          // navigated to the case
  });
});

describe("run-the-bank controls", () => {
  it("lists switches and switches a connector off with a reason", async () => {
    const calls = mockApi({
      "GET /switches": [{ kind: "capability", target: "fin.variance-commentary", off: true, reason: "reporting freeze", set_by: "carol", set_at: "2026-10-04T07:00:00Z", can_switch: true, history: [] }],
      "GET /capabilities": [],
      "GET /platform": { steps: [], connectors: [{ id: "gl", name: "GL", transport: "inproc", classification: "internal", tools: [] }], llm: "stub", entitlement: "dev" },
      "POST /switches": { ok: true },
    });
    renderAt("/", "/", <SwitchesPanel />);
    expect(await screen.findByText("reporting freeze")).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Switch kind"), "connector");
    await userEvent.selectOptions(screen.getByLabelText("Switch target"), "gl");
    await userEvent.type(screen.getByLabelText("Switch reason"), "GL outage INC-4411");
    await userEvent.click(screen.getByRole("button", { name: "Switch off" }));
    await waitFor(() => expect(calls.find((c) => c.method === "POST")?.body).toEqual({ kind: "connector", target: "gl", off: true, reason: "GL outage INC-4411" }));
  });

  it("lists schedules with their next run", async () => {
    mockApi({ "GET /schedules": [{ capability_id: "recon.investigation", team_group: "cats-motif", schedule: "30 6 * * 1-5", next_run: "2026-10-05T06:30:00Z", opens_as: "aof-scheduler", keys: [{}, {}], timezone: "UTC" }] });
    renderAt("/", "/", <SchedulesPanel />);
    expect(await screen.findByText("30 6 * * 1-5")).toBeInTheDocument();
    expect(screen.getByText(/2 case\(s\) each run, as aof-scheduler/)).toBeInTheDocument();
  });
});

describe("evidence", () => {
  it("uploads a file into the case", async () => {
    const c = { case_id: "fin.c1", evidence: [], status: "awaiting_review", can_decide: true } as unknown as CaseDetail;
    const calls = mockApi({ "POST /cases/fin.c1/evidence": { case: { ...c, evidence: [] } } });
    renderAt("/", "/", <EvidencePanel c={c} canUpload />);
    const file = new File(["%PDF-1.4"], "support.pdf", { type: "application/pdf" });
    await userEvent.upload(screen.getByLabelText("Evidence file"), file);
    await waitFor(() => expect(calls.some((x) => x.path === "/cases/fin.c1/evidence")).toBe(true));
    expect(screen.getByRole("button", { name: /Evidence pack/ })).toBeInTheDocument();
  });
});

describe("developer tools", () => {
  it("draws the workflow from the manifest", async () => {
    mockApi({ "GET /capabilities/fin/flow": { capability_id: "fin", name: "F", edges: [], opens: { on: "schedule", schedule: "0 7 2 * *", events: false },
      nodes: [{ id: "load", gate: false, pause: false, tools: ["gl.balances"], notes: [], people: [] },
              { id: "review", gate: true, pause: true, tools: [], notes: [], people: ["FIN_REVIEWER"] }] } });
    renderAt("/", "/", <FlowDiagram capabilityId="fin" />);
    const review = await screen.findByTestId("flow-review");
    expect(within(review).getByText("FIN_REVIEWER")).toBeInTheDocument();
    expect(within(review).getByText("People decide")).toBeInTheDocument();             // plain words, not step ids
    expect(within(screen.getByLabelText("At a glance")).getByText(/Get the data/)).toBeInTheDocument();
    expect(within(screen.getByTestId("flow-load")).getByText("gl.balances")).toBeInTheDocument();
    expect(screen.getByText("0 7 2 * *")).toBeInTheDocument();
  });

  it("runs an eval and shows agreement", async () => {
    const calls = mockApi({
      "GET /capabilities/fin/evals": [{ run_id: "r1", capability_id: "fin", version: 2, team_group: null, group_version: null, status: "done", started_by: "carol", started_at: "2026-10-04T07:00:00Z", finished_at: null, error: null,
        summary: { cases: 4, groups_compared: 12, agree: 9, disagree: 1, escalated: 2, missing: 0, new: 0, agreement_rate: 0.75, verdict_match_rate: null, wording_mean: 0.62, cost_usd: 1.2 } }],
      "POST /capabilities/fin/evals": {},
    });
    renderAt("/", "/", <EvalsPanel capabilityId="fin" versions={[1, 2]} groups={[]} />);
    expect(await screen.findByText("75%")).toBeInTheDocument();                       // agree with people
    expect(screen.getByText(/12 decisions in 4 past cases/)).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Eval version"), "2");
    await userEvent.click(screen.getByRole("button", { name: "Run eval" }));
    await waitFor(() => expect(calls.find((c) => c.method === "POST")?.body).toEqual({ version: 2, team_group: null }));
  });

  it("shows what changed between two versions", async () => {
    mockApi({ "GET /capabilities/fin/versions/1/diff/2": { diff: "--- fin v1\n+++ fin v2\n-  skill: old\n+  skill: new", changed: ["reasoning.skill"] } });
    const v = (n: number, status: string) => ({ version: n, status, note: "", drafted_by: "carol", drafted_at: "2026-10-04T07:00:00Z", decided_by: null, decided_at: null });
    renderAt("/", "/", <VersionsPanel capabilityId="fin" versions={[v(1, "active"), v(2, "draft")]} />);
    expect(await screen.findByText(/changed: reasoning.skill/)).toBeInTheDocument();
    expect(screen.getByLabelText("Version diff")).toHaveTextContent("+ skill: new");
  });
});
