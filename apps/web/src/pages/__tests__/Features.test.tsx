import { describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { InboxRow } from "../../api/helix";
import { mockApi, renderAt } from "../../test/render";
import InboxPage from "../Inbox";

const row = (id: string, extra: Partial<InboxRow> = {}): InboxRow => ({
  case_id: id,
  capability_id: "recon.investigation",
  capability_name: "Reconciliation investigation",
  case_label: "Rec run",
  subject: id,
  status: "awaiting_review",
  team_group: "cats-motif",
  opened_at: "2026-10-01T06:30:00Z",
  opened_by: "helix-scheduler",
  groups: 2,
  proposed: 2,
  escalated: 0,
  decided: 0,
  action: "review",
  ...extra,
});

describe("Inbox", () => {
  it("puts the most urgent first and filters to what needs confirmation", async () => {
    mockApi({
      "GET /inbox": [
        row("PRIME-MB-01", { due_state: "on_time", due_at: "2026-10-09T11:00:00Z", exposure: 10 }),
        row("PRIME-MB-04", { due_state: "overdue", due_at: "2026-10-01T11:00:00Z", needs_confirmation: 1, exposure: 538284.17, unit: "GBP" }),
        row("RATES-LDN-01", { acting_for: "rita" }),
      ],
      "GET /me/delegations": { away: [], covering: [] },
      "GET /dev/users": [],
    });
    renderAt("/inbox", "/inbox", <InboxPage />);
    const links = await screen.findAllByRole("link");
    expect(links.map((l) => l.textContent)).toEqual(["Rec run: PRIME-MB-04", "Rec run: PRIME-MB-01", "Rec run: RATES-LDN-01"]);
    expect(screen.getByText("538,284.17 GBP")).toBeInTheDocument();
    expect(screen.getByText(/for rita/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Needs confirmation/ }));
    expect(screen.getAllByRole("link").map((l) => l.textContent)).toEqual(["Rec run: PRIME-MB-04"]);
  });

  it("hands reviews to a colleague until a date", async () => {
    const calls = mockApi({
      "GET /inbox": [],
      "GET /me/delegations": { away: [], covering: [] },
      "GET /dev/users": [{ user_id: "raj", name: "Raj", roles: ["FOBO_RATES_CONTROLLER"] }],
      "POST /me/delegations": { delegation_id: "d1", from_user: "rita", to_user: "raj", starts_at: "", until: "", reason: null, active: true },
    });
    renderAt("/inbox", "/inbox", <InboxPage />);
    await userEvent.click(await screen.findByRole("button", { name: /Hand over my reviews/ }));
    await userEvent.selectOptions(await screen.findByLabelText(/Colleague/), "raj");
    await userEvent.type(screen.getByLabelText(/Reason/), "Annual leave");
    await userEvent.click(screen.getByRole("button", { name: "Hand over" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
    expect(calls.find((c) => c.method === "POST")!.body).toMatchObject({ to_user: "raj", reason: "Annual leave" });
  });
});

describe("Inbox on a phone", () => {
  it("shows each case as a card with what it needs and how urgent it is", async () => {
    const original = window.matchMedia;
    window.matchMedia = ((q: string) => ({ matches: q.includes("max-width"), media: q, addEventListener() {}, removeEventListener() {} })) as unknown as typeof window.matchMedia;
    try {
      mockApi({
        "GET /inbox": [row("PRIME-MB-04", { due_state: "overdue", due_at: "2026-10-01T11:00:00Z", needs_confirmation: 1 })],
        "GET /me/delegations": { away: [], covering: [] },
        "GET /dev/users": [],
      });
      renderAt("/inbox", "/inbox", <InboxPage />);
      const card = await screen.findByRole("link", { name: /PRIME-MB-04/ });
      expect(within(card).getByText("1 to confirm")).toBeInTheDocument();
      expect(within(card).getByText(/Overdue/)).toBeInTheDocument();
      expect(screen.queryByRole("table")).not.toBeInTheDocument();
    } finally {
      window.matchMedia = original;
    }
  });
});

describe("Questions for you", () => {
  it("shows the trader only the breaks asked about, and sends the answer", async () => {
    const calls = mockApi({
      "GET /inbox": [],
      "GET /me/delegations": { away: [], covering: [] },
      "GET /dev/users": [],
      "GET /requests": [{ request_id: "r1", case_id: "c1", group_id: "K", target: "desk", target_name: "Prime desk (trader)",
        question: "Was the IRS swap rebooked?", asked_by: "frank", asked_at: "2026-10-05T09:00:00Z", status: "open",
        answer: null, answered_by: null, answered_at: null, can_answer: true, subject: "PRIME-MB-04 · COB 2026-09-24",
        case_label: "Break run", group_label: "Aged break", columns: ["instrument", "difference"],
        rows: [{ instrument: "IRS 5Y USD", difference: -85.5 }] }],
      "POST /requests/r1/answer": { request_id: "r1", status: "answered" },
    });
    renderAt("/inbox", "/inbox", <InboxPage />);
    expect(await screen.findByText(/Was the IRS swap rebooked/)).toBeInTheDocument();
    expect(screen.getByText("IRS 5Y USD")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Your answer"), "Yes, on Friday");
    await userEvent.click(screen.getByRole("button", { name: /Answer/ }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
    expect(calls.find((c) => c.method === "POST")!.body).toEqual({ answer: "Yes, on Friday" });
  });
});
