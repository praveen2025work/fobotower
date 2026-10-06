import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { CaseDetail, Group } from "../../../api/aof";
import { renderAt } from "../../../test/render";
import { CaseLinks, GroupSteps } from "../StepsV2";

const group = {
  group_id: "g1", label: "Account 6100", group_key: { account: "6100" }, item_ids: [], priors: [], decision: null,
  approvals: { needed: 2, by: ["bob"], settled: false },
  finding: {
    status: "proposed", decided_by: "rule", comment: "Accrue",
    authority: { label: "over 250k", roles: ["FIN_REVIEWER"], approvals: 2, lane: "enhanced", bulk: false, source: "authority" },
    reserved: { roles: ["COMPLAINTS_LEAD"], reason: "redress above the handler's limit" },
    entries: { journal_id: "JE-1", period: "2026-09", balanced: true, problems: [], debits: 10, credits: 10,
      lines: [{ account: "6100", side: "debit", amount: 10, narrative: "GRNI" }, { account: "2150", side: "credit", amount: 10, narrative: "GRNI" }] },
    sent_message: { to: "client", subject: "We have received your complaint", body: "Thank you", message_id: "M1", approved_by: "carla" },
  },
} as unknown as Group;

describe("steps v2 on a case", () => {
  it("shows who may approve, how many, the journal and the message sent", () => {
    renderAt("/", "/", <GroupSteps group={group} />);
    expect(screen.getByText(/over 250k: fin reviewer · 2 different people · enhanced lane · one by one/)).toBeTruthy();
    expect(screen.getByText(/Reserved for complaints lead/)).toBeTruthy();
    expect(screen.getByText("1 of 2 approvals (bob)")).toBeTruthy();
    expect(screen.getByText(/Journal JE-1/)).toBeTruthy();
    expect(screen.getByText("balanced")).toBeTruthy();
    expect(screen.getByText(/approved by carla/)).toBeTruthy();
  });

  it("links the parent and children and shows the clocks", () => {
    const c = {
      parent_case_id: "p1",
      children: [{ case_id: "k1", subject: "PX-1", status: "completed", outcome: "completed", capability_id: "x" },
        { case_id: "k2", subject: "PX-2", status: "awaiting_review", outcome: null, capability_id: "x" }],
      clocks: [{ id: "final", label: "Final response", due_at: "2000-01-01T00:00:00Z", warn_before_hours: 4, warned: true, breached: true }],
    } as unknown as CaseDetail;
    renderAt("/", "/", <CaseLinks c={c} />);
    expect(screen.getByRole("link", { name: "its parent case" }).getAttribute("href")).toBe("/cases/p1");
    expect(screen.getByText(/1 of 2 finished/)).toBeTruthy();
    expect(screen.getByText(/breached/)).toBeTruthy();
  });
});
