import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path: string): string =>
  readFileSync(new URL(path, import.meta.url), "utf8");

const sources = {
  lead: read("../app/(dashboard)/truong-ca/page.tsx"),
  schedule: read("../app/(dashboard)/schedule/page.tsx"),
  official: read("../app/(dashboard)/schedule/OfficialRosterTable.tsx"),
  register: read("../app/(dashboard)/schedule/RosterRegisterTable.tsx"),
  week: read("../app/(dashboard)/schedule/WeekKanban.tsx"),
  editPage: read("../app/(dashboard)/schedule/edit/page.tsx"),
  editor: read("../app/(dashboard)/schedule/edit/RosterEditor.tsx"),
  sessions: read("../app/(dashboard)/work-sessions/page.tsx"),
  reports: read("../app/(dashboard)/reports/page.tsx"),
  print: read("../app/(dashboard)/reports/PrintReportButton.tsx"),
  ops: read("../app/(dashboard)/ops/OpsCenter.tsx"),
  telemetry: read("../app/(dashboard)/ops/telemetry/page.tsx"),
  settings: read("../app/(dashboard)/settings/page.tsx"),
  account: read("../app/(dashboard)/settings/AccountActions.tsx"),
  newUserPage: read("../app/(dashboard)/settings/new-user/page.tsx"),
  newUserForm: read("../app/(dashboard)/settings/new-user/NewUserForm.tsx"),
};

test("all operational and admin routes use the ClinicAI V2 page shell", () => {
  for (const key of [
    "lead",
    "schedule",
    "editPage",
    "sessions",
    "reports",
    "ops",
    "telemetry",
    "settings",
    "newUserPage",
  ] as const) {
    assert.match(sources[key], /page-in/,
      `${key} must opt into the V2 page shell`);
  }
});

test("the shift-lead overview mirrors the reference hierarchy with real visit data", () => {
  assert.match(sources.lead, /aria-label="Tổng quan điều phối"/);
  for (const label of [
    "Lượt khám hôm nay",
    "Đã tiếp nhận",
    "Đã thanh toán",
    "Cần theo dõi",
    "Danh sách lượt khám",
  ]) {
    assert.match(sources.lead, new RegExp(label));
  }
  assert.match(sources.lead, /rows\.filter/);
  assert.match(sources.lead, /payRes\.error == null && rxRes\.error == null/);
  assert.match(sources.lead, /paymentDataAvailable[\s\S]*?"—"/);
  assert.match(sources.lead, /!paymentDataAvailable[\s\S]*?Danh sách được tạm ẩn/);
  assert.doesNotMatch(sources.lead, /146|38|18\s*\/\s*22/);
});

test("operational views use project tokens instead of legacy and hard-coded palettes", () => {
  for (const [name, source] of Object.entries(sources)) {
    assert.doesNotMatch(source, /#[0-9a-fA-F]{3,8}\b/, `${name} has a hex colour`);
    assert.doesNotMatch(
      source,
      /(?:bg|text|border|ring|from|to|via)-(?:pink|zinc|slate|gray|emerald|amber|red|blue)-/,
      `${name} has a legacy palette utility`,
    );
    assert.doesNotMatch(source, /bg-white\b/, `${name} must use bg-surface`);
    assert.doesNotMatch(source, /bg-black\b|text-white\b/, `${name} bypasses colour tokens`);
    assert.doesNotMatch(source, /shadow-\[/, `${name} must use a shadow token`);
  }
});

test("dense operational tables remain reachable on narrow content widths", () => {
  for (const key of ["official", "register", "sessions", "reports", "telemetry", "settings"] as const) {
    assert.match(
      sources[key],
      /overflow-x-auto|overflow-auto/,
      `${key} needs an explicit horizontal scroll boundary`,
    );
  }
  assert.match(sources.schedule, /min-w-0/);
  assert.match(sources.ops, /minmax\(0,1fr\)/);
  assert.match(sources.register, /role="dialog"/);
  assert.match(sources.register, /aria-modal="true"/);
  assert.match(sources.register, /max-h-\[calc\(100dvh-2rem\)\]/);
  assert.match(sources.register, /event\.key === "Escape"/);
  assert.match(sources.register, /event\.key !== "Tab"/);
  assert.match(sources.register, /dialogRef\.current\?\.contains/);
});

test("existing authorization and mutation boundaries stay in place", () => {
  assert.match(sources.lead, /requireNavAccess\("\/truong-ca"\)/);
  assert.match(sources.sessions, /requireNavAccess\("\/work-sessions"\)/);
  assert.match(sources.ops, /fetch\("\/api\/ops\/summary"/);
  assert.match(sources.editor, /fetch\("\/api\/roster"/);
  assert.match(sources.account, /\/api\/admin\/users/);
  assert.match(sources.newUserForm, /\/api\/admin\/users/);
  assert.match(sources.settings, /isAdminRole\(role\)/);
  assert.match(sources.reports, /isOpsAdmin\(role\)/);
});
