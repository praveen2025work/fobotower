import { screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { mockApi, renderAt } from "../../test/render";
import InboxPage from "../Inbox";

afterEach(() => vi.unstubAllGlobals());

it("lists cases waiting on me across capabilities, linking to each workspace", async () => {
  mockApi({
    "GET /inbox": [
      { case_id: "fin.c1", capability_id: "fin.variance-commentary", capability_name: "P&L variance commentary", case_label: "Lane", subject: "UK01 · 2026-09", status: "awaiting_review", opened_at: "2026-10-03T10:00:00Z", opened_by: "alice", groups: 4, proposed: 3, escalated: 1, decided: 0, action: "review" },
      { case_id: "cash.c2", capability_id: "cash.bank-vs-ledger", capability_name: "Cash — bank vs ledger", case_label: "Rec run", subject: "UK01 · 2026-10-02", status: "awaiting_publish", opened_at: "2026-10-03T09:00:00Z", opened_by: "dan", groups: 3, proposed: 3, escalated: 0, decided: 3, action: "release" },
    ],
  });
  renderAt("/inbox", "/inbox", <InboxPage />);
  const lane = await screen.findByRole("link", { name: "Lane: UK01 · 2026-09" });
  expect(lane).toHaveAttribute("href", "/cases/fin.c1");
  expect(screen.getByText("Rec run: UK01 · 2026-10-02")).toBeInTheDocument();
  expect(screen.getByText(/1 escalated/)).toBeInTheDocument();
});

it("says when nothing is waiting", async () => {
  mockApi({ "GET /inbox": [] });
  renderAt("/inbox", "/inbox", <InboxPage />);
  expect(await screen.findByText("Nothing is waiting on you.")).toBeInTheDocument();
});

it("folds many tasks of one agent and COB into one row that opens the agent's summary", async () => {
  const row = (n: number) => ({
    case_id: `recon.${n}`, capability_id: "recon.investigation", capability_name: "Helix FOBO Agent", case_label: "CATS vs MOTIF",
    subject: `FI Credit APAC · Asia IG bonds (FIC-APAC-${n}) · COB 2026-10-20`, status: "awaiting_review",
    opened_at: "2026-10-21T06:00:00Z", opened_by: "aof-scheduler", groups: 2, proposed: 2, escalated: n === 1 ? 1 : 0,
    decided: 0, action: "review", team_group: "cats-motif-fi-credit", summary_date: "2026-10-20", exposure: 1000, unit: "GBP",
  });
  mockApi({
    "GET /inbox": [
      ...Array.from({ length: 7 }, (_, i) => row(i + 1)),
      { ...row(99), case_id: "rates.1", team_group: "cats-motif-rates", subject: "USD swaps (RATES-LDN-01) · COB 2026-10-20" },
    ],
  });
  renderAt("/inbox", "/inbox", <InboxPage />);
  const run = await screen.findByRole("link", { name: /CATS vs MOTIF · 2026-10-20: 7 tasks/ });
  expect(run).toHaveAttribute("href", "/capabilities/recon.investigation?tab=summary&date=2026-10-20");
  expect(screen.getByText("14 of 14 to decide")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "CATS vs MOTIF: USD swaps (RATES-LDN-01) · COB 2026-10-20" })).toHaveAttribute("href", "/cases/rates.1");
  expect(screen.queryByText(/FIC-APAC-3\)/)).not.toBeInTheDocument();
});
