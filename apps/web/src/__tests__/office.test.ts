// @vitest-environment node
import { execFileSync } from "node:child_process";
import path from "node:path";
import { expect, test } from "vitest";

// The office form of the console (office/aos-frontend) is committed; it must be what
// office/convert.mjs makes from the console today. If this fails: npm run office:build.
test("office/aos-frontend matches the console", () => {
  const web = path.resolve(__dirname, "../..");
  expect(() => execFileSync("node", ["office/convert.mjs", "--check"], { cwd: web, stdio: "pipe" })).not.toThrow();
}, 60_000);
