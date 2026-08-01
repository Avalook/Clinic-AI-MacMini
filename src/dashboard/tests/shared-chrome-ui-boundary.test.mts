import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = (path: string) =>
  readFileSync(new URL(path, import.meta.url), "utf8");

test("shared chrome uses the ClinicAI token system instead of a second palette", () => {
  const badge = source("../app/(dashboard)/StatusBadge.tsx");
  const pane = source("../app/(dashboard)/SplitPane.tsx");
  const notice = source("../app/(dashboard)/DeclinedNotice.tsx");
  const bottomNav = source("../app/(dashboard)/BottomNav.tsx");
  const nav = source("../app/(dashboard)/Nav.tsx");
  const brief = source("../app/(dashboard)/PreVisitBrief.tsx");
  const roster = source("../lib/roster.ts");

  assert.match(badge, /bg-status-ready-bg text-status-ready/);
  assert.match(badge, /rounded-chip/);
  assert.match(pane, /w-px bg-line/);
  assert.match(notice, /border-danger bg-surface/);
  assert.match(bottomNav, /shadow-panel/);
  assert.match(nav, /text-brand-700/);
  assert.match(brief, /bg-brand-600/);
  assert.match(brief, /border-danger bg-danger-bg/);

  for (const content of [badge, pane, notice, bottomNav, nav, brief, roster]) {
    assert.doesNotMatch(content, /#[0-9a-fA-F]{3,8}/);
    assert.doesNotMatch(content, /pink|rose|fuchsia|rgba/i);
  }
});
