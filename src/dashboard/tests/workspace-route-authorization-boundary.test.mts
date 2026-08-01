import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const page = (path: string) =>
  readFileSync(new URL(path, import.meta.url), "utf8");

const protectedWorkspaces = [
  ["../app/(dashboard)/reception/queue/page.tsx", "/reception/queue"],
  ["../app/(dashboard)/doctor/board/page.tsx", "/doctor/board"],
  ["../app/(dashboard)/cashier/board/page.tsx", "/cashier/board"],
  ["../app/(dashboard)/doctor/orders/[visitId]/page.tsx", "/doctor/board"],
] as const;

test("every role-scoped workspace has a server-side navigation guard", () => {
  for (const [path, href] of protectedWorkspaces) {
    const source = page(path);
    assert.match(
      source,
      /import \{ requireNavAccess \} from "@\/lib\/clinic-session"/,
      `${path} must import the server-side guard`,
    );
    assert.match(
      source,
      new RegExp(`await requireNavAccess\\("${href}"\\)`),
      `${path} must authorize before it reads workspace data`,
    );
  }
});
