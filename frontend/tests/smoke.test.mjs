import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";


test("login page contains app title", async () => {
  const pageSource = await readFile("app/page.tsx", "utf8");

  assert.ok(pageSource.includes("JobMatch"));
});
