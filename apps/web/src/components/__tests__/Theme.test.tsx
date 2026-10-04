import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { fireEvent, screen } from "@testing-library/react";

import Layout from "../Layout";
import { mockApi, renderAt } from "../../test/render";

describe("Barclays themes", () => {
  beforeEach(() => {
    localStorage.clear();
    delete document.documentElement.dataset.theme;
    mockApi({ "GET /v1/platform": { llm: "stub", entitlement: "fixture" } });
  });
  afterEach(() => localStorage.clear());

  it("starts light, switches to dark and remembers the choice", () => {
    renderAt("/", "/", <Layout onUserChange={() => {}} />);
    expect(document.documentElement.dataset.theme).toBe("light");

    fireEvent.click(screen.getByRole("button", { name: "Switch to dark theme" }));
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem("helix.theme")).toBe("dark");

    fireEvent.click(screen.getByRole("button", { name: "Switch to light theme" }));
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("starts light even when the device is set to dark", () => {
    const original = window.matchMedia;
    window.matchMedia = ((q: string) => ({ matches: q.includes("dark"), media: q, addEventListener() {}, removeEventListener() {} })) as unknown as typeof window.matchMedia;
    try {
      renderAt("/", "/", <Layout onUserChange={() => {}} />);
      expect(document.documentElement.dataset.theme).toBe("light");
    } finally {
      window.matchMedia = original;
    }
  });

  it("opens in the saved theme", () => {
    localStorage.setItem("helix.theme", "dark");
    renderAt("/", "/", <Layout onUserChange={() => {}} />);
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(screen.getByRole("button", { name: "Switch to light theme" })).toBeInTheDocument();
  });
});
