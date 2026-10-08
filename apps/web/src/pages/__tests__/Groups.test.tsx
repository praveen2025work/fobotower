import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import type { Manifest, TeamGroup } from "../../api/aof";
import { mockApi, renderAt } from "../../test/render";
import CapabilityDetail from "../CapabilityDetail";
import GroupDetail from "../GroupDetail";

afterEach(() => vi.unstubAllGlobals());

const manifest = {
  id: "recon.investigation", name: "Reconciliation investigation", description: "Match two systems.",
  owners: { people: ["erin"], role: "AOF_RECON_OWNER", four_eyes: true },
  case: { label: "Rec run", item_label: "Break", key: ["entity", "date"], subject: null, scopes: { entity: "entity" }, opens_on: "manual" },
  items: { load: null, id_field: "ref", amount_field: "difference", display: [], in_scope: null },
  steps: ["match", "group", "reason", "draft", "validate", "review", "record"], pause_before: ["review"],
  group_by: ["counterparty"], policy: {}, rules: [],
  reasoning: { reasoner: "llm", skill: "Investigate.", tools: [], output: "verdict" },
  review: { roles: ["CASH_OPS"] }, publish: null, match: null,
  configurable: ["case.key", "match", "policy.*", "review.roles"],
} as unknown as Manifest;

const group = (g: string, name: string, key: string[], extra: Partial<TeamGroup> = {}): TeamGroup => ({
  capability_id: "recon.investigation", group: g, name, description: "", version: 1,
  owners: { people: [], role: null, four_eyes: true }, sets: ["case.key", "match"],
  case_label: "Rec run", item_label: "Break", case_key: key, review_roles: ["FOBO_CONTROLLER"],
  is_owner: false, can_open: true, can_decide: true, ...extra,
});

it("shows each team's group, and opens a case under the chosen group with its own key", async () => {
  const calls = mockApi({
    "GET /capabilities/recon.investigation": { version: 1, manifest, versions: [] },
    "GET /capabilities/recon.investigation/groups": [
      group("cats-motif", "CATS vs MOTIF (FOBO)", ["book", "cob"]),
      group("cash-bank-ledger", "Cash — bank vs ledger", ["entity", "date"], { can_open: false }),
    ],
    "GET /capabilities/recon.investigation/cases": [],
    "POST /capabilities/recon.investigation/cases": { case_id: "recon.c1" },
  });
  renderAt("/capabilities/recon.investigation", "/capabilities/:id", <CapabilityDetail />);
  await userEvent.click(await screen.findByRole("tab", { name: "groups" }));        // Cases open first
  expect(await screen.findByText("CATS vs MOTIF (FOBO)")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("tab", { name: "Cases" }));
  await userEvent.click(screen.getByRole("button", { name: /Open a/ }));          // folded until asked for
  // only groups the user may open are offered; the key fields are that group's
  const picker = within(screen.getByLabelText("Group"));
  expect(picker.getByRole("option", { name: "CATS vs MOTIF (FOBO)" })).toBeInTheDocument();
  expect(picker.queryByRole("option", { name: "Cash — bank vs ledger" })).not.toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("book"), "PRIME-MB-01");
  await userEvent.type(screen.getByLabelText("cob"), "2026-08-03");
  await userEvent.click(screen.getByRole("button", { name: /Open and run/ }));
  await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
  expect(calls.find((c) => c.method === "POST")!.body).toEqual({
    case_key: { book: "PRIME-MB-01", cob: "2026-08-03" }, team_group: "cats-motif",
  });
});

it("lets a group owner change the group as a draft for another owner to approve", async () => {
  const detail = {
    ...group("cats-motif", "CATS vs MOTIF (FOBO)", ["book", "cob"], { is_owner: true }),
    config: { group: "cats-motif", name: "CATS vs MOTIF (FOBO)", description: "", owners: { people: ["frank"], role: null, four_eyes: true },
              set: { policy: { auto_adjust_limit: { value: 250, unit: "USD" } } } },
    manifest, configurable: manifest.configurable,
    versions: [{ version: 1, status: "active", note: "", drafted_by: "system:seed", drafted_at: "2026-10-03T10:00:00Z", decided_by: "system:seed", decided_at: null }],
  };
  const calls = mockApi({
    "GET /capabilities/recon.investigation/groups/cats-motif": detail,
    "POST /capabilities/recon.investigation/groups": { group_id: "cats-motif", version: 2 },
  });
  renderAt("/capabilities/recon.investigation/groups/cats-motif", "/capabilities/:id/groups/:group", <GroupDetail />);
  const editor = await screen.findByLabelText(/Settings \(YAML\)/);
  expect((editor as HTMLTextAreaElement).value).toContain("auto_adjust_limit");
  await userEvent.clear(editor);
  await userEvent.type(editor, "policy:{enter}  auto_adjust_limit:{enter}    value: 999");
  await userEvent.click(screen.getByRole("button", { name: /Submit for approval/ }));
  const isDraft = (c: { method: string; path: string }) => c.method === "POST" && c.path.endsWith("/groups");
  await waitFor(() => expect(calls.some(isDraft)).toBe(true));
  const body = calls.find(isDraft)!.body as { config: { set: unknown; owners: unknown } };
  expect(body.config.set).toEqual({ policy: { auto_adjust_limit: { value: 999 } } });
  expect(body.config.owners).toEqual(detail.config.owners);                      // owners are not edited here
  expect(await screen.findByText(/Version 2 drafted/)).toBeInTheDocument();
});
