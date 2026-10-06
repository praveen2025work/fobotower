import { describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { parse } from "yaml";

import { mockApi, renderAt } from "../../../test/render";
import OrchestratorEditor from "../OrchestratorEditor";
import { groupSet } from "../paths";

const manifest = {
  id: "recon.investigation", name: "Reconciliation investigation", description: "",
  owners: { people: ["erin"], role: null, four_eyes: true },
  case: { label: "Rec run", item_label: "Break", key: ["book", "cob"], subject: "{book} · COB {cob}", scopes: { book: "book" }, opens_on: "manual", schedule: null, schedule_keys: [], events: false, opens_as: null, due: null },
  items: { load: null, id_field: "instrument", amount_field: "difference", amount_unit: "GBP", display: [], in_scope: null },
  match: { left: { tool: "cats.positions", args: { book: "$case.book" } }, right: { tool: "motif.positions", args: { book: "$case.book" } }, keys: ["instrument"], amount_field: "mtm", tolerance: 0.5, left_label: "cats", right_label: "motif" },
  policy: { materiality_threshold: { value: null, unit: "GBP" } },
  steps: ["match", "enrich", "group", "reason", "draft", "validate", "review", "record"],
  pause_before: ["review"],
  enrich: [{ tool: "motif.break_snapshots", args: { book: "$case.book" }, keys: ["instrument"], prefix: "" }],
  group_by: ["category"], group_label: null, rules: [],
  reasoning: { reasoner: "llm", skill: "Investigate.", tools: ["motif.booking_events"], specialists: [], output: "verdict" },
  review: { roles: ["FOBO_CONTROLLER"], require_comment: ["reject"], confirm: "tick_and_comment", bulk_exclude: ["confirmation"], dual_review_when: null, max_reinvestigations: 2, opener_may_decide: true, allow_delegation: false },
  publish: null, playbook: null, knowledge: { entities: [], reference: null, as_of: null, priors_lookback_days: null }, resolve: [],
  metrics: { manual_minutes_per_item: 12 }, limits: {}, insights: {}, escalation: null, export: { columns: [] }, retention: null,
  configurable: ["policy.*", "review.roles"],
};

const platform = {
  steps: [], llm: "stub", entitlement: "dev-stub",
  connectors: [{ id: "motif", name: "MOTIF", transport: "inproc", classification: "internal", tools: [
    { name: "motif.booking_events", description: "Booking events", access: "read", scope: null },
    { name: "motif.break_snapshots", description: "Snapshots", access: "read", scope: null },
  ] }],
};

describe("Orchestrator editor", () => {
  it("lets a group owner change only what the group may set, checked as they go, as a draft", async () => {
    const config = { group: "cats-motif", name: "CATS vs MOTIF", description: "", owners: { people: ["frank"], role: null, four_eyes: true },
      set: { review: { roles: ["FOBO_CONTROLLER"] } } };
    const calls = mockApi({
      "GET /platform": platform,
      "POST /capabilities/recon.investigation/check": { ok: true, problems: [] },
      "POST /capabilities/recon.investigation/groups": { group_id: "cats-motif", version: 3 },
    });
    renderAt("/", "/", <OrchestratorEditor capabilityId="recon.investigation" manifest={manifest}
      mode={{ kind: "group", config, configurable: manifest.configurable }} canEdit />);

    expect(await screen.findByText("Passes every platform check")).toBeInTheDocument();
    // the workflow is the capability's: its steps cannot be switched by a group
    await userEvent.click(screen.getByRole("button", { name: /Enrich/ }));
    expect(screen.getByRole("checkbox", { name: /This step runs/ })).toBeDisabled();
    // a threshold is the group's to set
    await userEvent.click(screen.getByRole("button", { name: /Thresholds/ }));
    const value = within(screen.getByRole("group", { name: "Thresholds" })).getByRole("textbox", { name: /Value/ });
    await userEvent.type(value, "250000");
    expect(screen.getByText("1 change")).toBeInTheDocument();
    await waitFor(() => expect(calls.some((c) => c.path.endsWith("/check") && JSON.stringify(c.body).includes("250000"))).toBe(true));

    await screen.findByText("Passes every platform check");
    await userEvent.click(screen.getByRole("button", { name: /Review and submit/ }));
    expect(screen.getByText("policy.materiality_threshold.value")).toBeInTheDocument();
    await userEvent.click(await screen.findByRole("button", { name: /Submit for approval/ }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/groups"))).toBe(true));
    const body = calls.find((c) => c.path.endsWith("/groups"))!.body as { config: { set: unknown } };
    expect(body.config.set).toEqual({
      review: { roles: ["FOBO_CONTROLLER"] },                                   // kept
      policy: { materiality_threshold: { value: 250000, unit: "GBP" } },         // added at its configurable path
    });
    expect(await screen.findByText(/Version 3 of this group drafted/)).toBeInTheDocument();
  });

  it("lets a capability owner switch steps and shows each problem on its step", async () => {
    const calls = mockApi({
      "GET /platform": platform,
      "POST /capabilities/recon.investigation/check": (body: unknown) => {
        const steps = ((body as { manifest: { steps: string[] } }).manifest.steps);
        return steps.includes("classify")
          ? { ok: false, problems: ["playbook.default_category `` is not a category"] }
          : { ok: true, problems: [] };
      },
      "POST /authoring/submit": { capability_id: "recon.investigation", version: 9 },
    });
    renderAt("/", "/", <OrchestratorEditor capabilityId="recon.investigation" manifest={manifest} mode={{ kind: "capability" }} canEdit />);
    await screen.findByText("Passes every platform check");

    // gates show as always on, with nothing to switch
    await userEvent.click(screen.getByRole("button", { name: /Human review/ }));
    expect(screen.queryByRole("checkbox", { name: /This step runs/ })).not.toBeInTheDocument();
    expect(screen.getByText(/always stops here for a person/)).toBeInTheDocument();

    // switching the playbook on: the server's problem lands on that step
    await userEvent.click(screen.getByRole("button", { name: /Playbook/ }));
    await userEvent.click(screen.getByRole("checkbox", { name: /This step runs/ }));
    expect(await screen.findByText(/1 problem to fix/)).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: /Playbook/ })).getByText(/default_category/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox", { name: /This step runs/ }));          // back off
    await screen.findByText("Passes every platform check");

    // a tollgate before the model: the run waits for a person, who is named
    await userEvent.click(screen.getByRole("button", { name: /Rules, then the model/ }));
    await userEvent.click(screen.getByRole("checkbox", { name: /Tollgate: a person approves/ }));
    await userEvent.type(screen.getByRole("textbox", { name: /What they check/ }), "Are both sides complete?");

    // switching enrich off, and submitting the whole manifest as a draft
    await userEvent.click(screen.getByRole("button", { name: /Enrich/ }));
    await userEvent.click(screen.getByRole("checkbox", { name: /This step runs/ }));
    await screen.findByText("Passes every platform check");
    await userEvent.click(screen.getByRole("button", { name: /Review and submit/ }));
    await userEvent.click(await screen.findByRole("button", { name: /Submit for approval/ }));
    await waitFor(() => expect(calls.some((c) => c.path === "/authoring/submit")).toBe(true));
    const sent = parse((calls.find((c) => c.path === "/authoring/submit")!.body as { yaml: string }).yaml);
    expect(sent.steps).toEqual(["match", "group", "reason", "draft", "validate", "review", "record"]);
    expect(sent.enrich).toEqual([]);
    expect(sent.pause_before).toEqual(["review", "reason"]);
    expect(sent.tollgates).toEqual({ reason: { roles: [], check: "Are both sides complete?", stop_needs_comment: true } });
  });

  it("is read-only for someone who does not own it", async () => {
    mockApi({ "GET /platform": platform });
    renderAt("/", "/", <OrchestratorEditor capabilityId="recon.investigation" manifest={manifest} mode={{ kind: "capability" }} canEdit={false} />);
    expect(await screen.findByText(/You can look; its owners change it/)).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /A case is called/ })).toBeDisabled();
  });
});

describe("groupSet", () => {
  it("writes a changed value at its configurable path and keeps the rest", () => {
    const before = { policy: { a: { value: 1 }, b: { value: 2 } }, review: { roles: ["X"], confirm: "tick" } };
    const after = { policy: { a: { value: 1 }, b: { value: 5 } }, review: { roles: ["Y"], confirm: "none" } };
    expect(groupSet({ case: { label: "Run" } }, ["policy.*", "review.roles"], before, after)).toEqual({
      case: { label: "Run" }, policy: { b: { value: 5 } }, review: { roles: ["Y"] },   // review.confirm is not the group's
    });
  });
});

describe("Prepare the data (configurable steps)", () => {
  it("adds a data step after the item source, sets it up, and keeps it when a core step is switched", async () => {
    const calls = mockApi({
      "GET /platform": platform,
      "POST /capabilities/recon.investigation/check": { ok: true, problems: [] },
      "POST /authoring/submit": { capability_id: "recon.investigation", version: 9 },
    });
    renderAt("/", "/", <OrchestratorEditor capabilityId="recon.investigation" manifest={manifest} mode={{ kind: "capability" }} canEdit />);
    await userEvent.click(await screen.findByRole("button", { name: /Prepare the data/ }));
    await userEvent.selectOptions(screen.getByLabelText("Step type to add"), "filter");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    const step = screen.getByRole("region", { name: "Step filter_1" });
    await userEvent.type(within(step).getByLabelText(/Keep items when/), "not is_test");
    // switching a core step off and on keeps the data step where it is
    await userEvent.click(screen.getByRole("button", { name: /Enrich/ }));
    await userEvent.click(screen.getByRole("checkbox", { name: /This step runs/ }));
    await userEvent.click(screen.getByRole("checkbox", { name: /This step runs/ }));
    await waitFor(() => expect(calls.some((c) => c.path.endsWith("/check") && JSON.stringify(c.body).includes("not is_test"))).toBe(true));
    const last = [...calls].reverse().find((c) => c.path.endsWith("/check"))!.body as { manifest: Record<string, unknown> };
    expect(last.manifest.steps).toEqual(["match", "filter_1", "enrich", "group", "reason", "draft", "validate", "review", "record"]);
    expect((last.manifest.step_settings as Record<string, { type: string; with: { keep_when: string } }>).filter_1)
      .toMatchObject({ type: "filter", with: { keep_when: "not is_test" } });
  });
});
