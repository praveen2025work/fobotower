import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import { mockApi, renderAt } from "../../test/render";
import Authoring from "../Authoring";

afterEach(() => vi.unstubAllGlobals());

it("drafts from a BRD, shows what to fix, and submits the edited manifest", async () => {
  const calls = mockApi({
    "GET /authoring/drafts": [],
    "POST /authoring/draft": {
      yaml: "id: draft.x\nsteps: [load]\n",
      manifest: null,
      problems: ["`validate` is required"],
      assumptions: ["no materiality threshold given"],
      author: "agent-sdk",
    },
    "POST /authoring/submit": { capability_id: "draft.x", version: 1 },
  });
  renderAt("/authoring", "/authoring", <Authoring />);
  await userEvent.click(screen.getByRole("tab", { name: /Describe it/ }));
  await userEvent.type(screen.getByLabelText("BRD"), "Monthly variance commentary");
  await userEvent.click(screen.getByRole("button", { name: /Draft capability/ }));

  expect(await screen.findByText("`validate` is required")).toBeInTheDocument();
  expect(screen.getByText("no materiality threshold given")).toBeInTheDocument();
  const editor = screen.getByLabelText(/Manifest \(YAML\)/);
  await userEvent.clear(editor);
  await userEvent.type(editor, "id: draft.x");
  await userEvent.click(screen.getByRole("button", { name: /Submit for approval/ }));
  await waitFor(() => expect(calls.some((c) => c.path === "/authoring/submit")).toBe(true));
  expect(calls.find((c) => c.path === "/authoring/submit")!.body).toMatchObject({ yaml: "id: draft.x" });
  expect(await screen.findByText(/goes live when another owner approves it/)).toBeInTheDocument();
});

it("lets a second owner approve a pending draft", async () => {
  const calls = mockApi({
    "GET /authoring/drafts": [
      { capability_id: "draft.x", version: 1, name: "Variance review", note: "", drafted_by: "carol", drafted_at: "2026-10-03T10:00:00Z", new: true, can_approve: true },
    ],
    "POST /capabilities/draft.x/versions/1/approve": { version: 1 },
  });
  renderAt("/authoring", "/authoring", <Authoring />);
  await userEvent.click(await screen.findByRole("button", { name: "Approve" }));
  await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
  expect(await screen.findByText(/now live/)).toBeInTheDocument();
});

it("builds a capability from answers with no model, and says when no model is connected", async () => {
  const calls = mockApi({
    "GET /authoring/drafts": [],
    "GET /authoring/modes": { guided: true, templates: true, brd_model: false, brd_author: "template",
      brd_note: "No model is connected here: a BRD only picks the nearest template." },
    "GET /platform": { steps: [], llm: "stub", entitlement: "dev-stub",
      connectors: [{ id: "mbrec", name: "MB Rec", transport: "inproc", classification: "confidential",
        tools: [{ name: "mbrec.breaks", description: "Open breaks", access: "read", scope: null }] }] },
    "POST /authoring/guided": { yaml: "id: draft.equities-breaks\n", manifest: null, problems: [],
      assumptions: ["No model: what the rules cannot settle goes straight to the reviewers."], author: "guided" },
  });
  renderAt("/authoring", "/authoring", <Authoring />);
  expect(screen.getByRole("tab", { name: /Answer questions/ })).toHaveAttribute("aria-selected", "true");
  await userEvent.type(screen.getByLabelText("Name"), "Equities breaks");
  await userEvent.click(screen.getByRole("button", { name: /Next: Case and data/ }));          // a short step at a time
  await userEvent.selectOptions(await screen.findByLabelText("Items come from"), "mbrec.breaks");
  await userEvent.click(screen.getByRole("button", { name: /Next: Who decides/ }));
  await userEvent.click(screen.getByLabelText("a person (no model)"));
  await userEvent.click(screen.getByRole("button", { name: /Next: Checks/ }));
  await userEvent.type(screen.getByLabelText(/Sign-off checklist/), "Is the root cause evidenced?");
  await userEvent.click(screen.getByRole("button", { name: /Build the capability/ }));
  await waitFor(() => expect(calls.some((c) => c.path === "/authoring/guided")).toBe(true));
  expect(calls.find((c) => c.path === "/authoring/guided")!.body).toMatchObject({
    name: "Equities breaks", kind: "investigate", source_tool: "mbrec.breaks", decided_by: "person",
    case_key: ["book", "cob"], checklist: ["Is the root cause evidenced?"] });
  expect(await screen.findByText(/drafted by guided/)).toBeInTheDocument();

  await userEvent.click(screen.getByRole("tab", { name: /Describe it/ }));
  expect(await screen.findByText(/No model is connected here/)).toBeInTheDocument();
});
