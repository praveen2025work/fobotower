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
