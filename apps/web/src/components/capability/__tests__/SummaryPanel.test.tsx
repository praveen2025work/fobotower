import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import { mockApi, renderAt } from "../../../test/render";
import SummaryPanel from "../SummaryPanel";

afterEach(() => vi.unstubAllGlobals());

const settle = (g: string, ready = true) => ({
  group_id: g, label: "Settlement break · back office", verdict: "POST", status: "proposed", items: 1, amount: 1000,
  flags: [], blockers: [], ready, needs_comment: false,
});
const judgement = (g: string) => ({
  group_id: g, label: "Price break · side not proven", verdict: null, status: "proposed", items: 1, amount: 500,
  flags: ["judgement"], blockers: ["judgement"], ready: false, needs_comment: false,
});
const task = (id: string, region: string, desk: string, status: string, open: unknown[], items = open.length) => ({
  case_id: id, subject: `FI Credit ${region} · Asia IG bonds (${id}) · COB 2026-10-20`, team_group: "cats-motif-fi-credit",
  status, outcome: null, facts: ["FI Credit", region, desk, "Asia IG bonds"], items, groups: open.length, settled: 0,
  exposure: null, unit: "GBP", due_at: null, due_state: null, can_decide: status === "awaiting_review", open,
});

const DAY = {
  capability_id: "recon.investigation", capability_name: "Helix FOBO Agent", case_label: "Reconciliation",
  dates: ["2026-10-20", "2026-10-19"], date: "2026-10-20",
  dimensions: [{ field: "book_business", label: "Business" }, { field: "book_region", label: "Region" },
               { field: "book_desk", label: "Desk" }, { field: "book_product", label: "Product" }],
  groups: [{ group: "cats-motif-fi-credit", name: "CATS vs MOTIF — FI Credit (FOBO)", case_label: "CATS vs MOTIF", checklist: [] }],
  tasks: [
    task("FIC-APAC-0001", "APAC", "FIC-APAC-IG", "awaiting_review", [settle("g1"), judgement("g2")]),
    task("FIC-APAC-0002", "APAC", "FIC-APAC-IG", "awaiting_review", [settle("g3")]),
    task("FIC-APAC-0003", "APAC", "FIC-APAC-HY", "completed", [], 0),
    task("FIC-EMEA-0001", "EMEA", "FIC-EMEA-IG", "awaiting_review", [settle("g4")]),
    task("FIC-EMEA-0002", "EMEA", "FIC-EMEA-IG", "completed", [], 0),
  ],
  totals: {},
};

it("groups the day by region, then narrows to one region's desks", async () => {
  mockApi({ "GET /capabilities/recon.investigation/summary": DAY });
  renderAt("/a", "/a", <SummaryPanel capabilityId="recon.investigation" />);
  expect(await screen.findByLabelText("Day totals")).toHaveTextContent("5 tasks · 2 clean · 3 waiting for review");
  await userEvent.click(screen.getByRole("tab", { name: "Region" }));
  const table = screen.getByRole("table");
  expect(within(table).getByRole("button", { name: /APAC/ })).toBeInTheDocument();
  await userEvent.click(within(table).getByRole("button", { name: /APAC/ }));
  expect(screen.getByLabelText("Filters")).toHaveTextContent("Region: APAC");
  expect(screen.getByRole("tab", { name: "Desk", selected: true })).toBeInTheDocument();
  expect(screen.getByLabelText("Day totals")).toHaveTextContent("3 tasks");
});

it("approves the same break across tasks once, leaving judgement calls for one by one", async () => {
  const calls = mockApi({
    "GET /capabilities/recon.investigation/summary": DAY,
    "POST /capabilities/recon.investigation/summary/decisions": { decided: 3, refused: [], refused_count: 0, reasons: [] },
  });
  renderAt("/a", "/a", <SummaryPanel capabilityId="recon.investigation" />);
  const patterns = await screen.findByLabelText("Patterns");
  expect(patterns).toHaveTextContent("Settlement break · back office");
  expect(patterns).toHaveTextContent("3 books · 3 breaks");
  expect(patterns).toHaveTextContent("one by one: 1 judgement call");
  await userEvent.click(within(patterns).getByRole("button", { name: "Approve 3" }));
  const approve = within(patterns).getAllByRole("button", { name: "Approve 3" }).at(-1)!;
  expect(approve).toBeDisabled();                                  // until the pattern is confirmed
  await userEvent.click(screen.getByRole("checkbox"));
  await userEvent.click(approve);
  expect(await screen.findByRole("status")).toHaveTextContent("Approved 3.");
  const sent = calls.find((c) => c.method === "POST")!.body as { targets: { case_id: string; group_ids: string[] }[]; action: string };
  expect(sent.action).toBe("approve");
  expect(sent.targets).toEqual([
    { case_id: "FIC-APAC-0001", group_ids: ["g1"] },
    { case_id: "FIC-APAC-0002", group_ids: ["g3"] },
    { case_id: "FIC-EMEA-0001", group_ids: ["g4"] },
  ]);
});

it("lists the tasks waiting first and opens one", async () => {
  mockApi({ "GET /capabilities/recon.investigation/summary": DAY });
  renderAt("/a", "/a", <SummaryPanel capabilityId="recon.investigation" />);
  const tasks = await screen.findByLabelText("Tasks");
  const links = within(tasks).getAllByRole("link");
  expect(links[0]).toHaveAttribute("href", "/cases/FIC-APAC-0001");
  expect(within(tasks).getAllByText("clean")).toHaveLength(2);
});
