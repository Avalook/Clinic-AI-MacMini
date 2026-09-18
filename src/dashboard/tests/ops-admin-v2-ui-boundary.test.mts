import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path: string): string =>
  readFileSync(new URL(path, import.meta.url), "utf8");

const sources = {
  lead: read("../app/(dashboard)/truong-ca/page.tsx"),
  schedule: read("../app/(dashboard)/schedule/page.tsx"),
  // Bảng lịch chính thức giờ chỉ là một dòng gọi sang bảng trang chủ (16/09/2026,
  // xem OfficialRosterTable.tsx). Khung cuộn ngang thật nằm ở ĐÓ — đọc tệp vỏ
  // thì bài kiểm đỏ oan, còn nới bài kiểm thì mất luôn thứ nó canh.
  official: read("../app/(dashboard)/home/WorkRosterTable.tsx"),
  register: read("../app/(dashboard)/schedule/RosterRegisterTable.tsx"),
  // WeekKanban.tsx và schedule/edit/* đều đã bị xoá (commit 410c989, 09/08/2026:
  // hai màn cùng ghi vào một bảng lịch trực). Đường ghi /api/roster mà `editor`
  // từng canh nay do `register` canh — cùng một API, một màn duy nhất.
  reports: read("../app/(dashboard)/reports/page.tsx"),
  print: read("../app/(dashboard)/reports/PrintReportButton.tsx"),
  ops: read("../app/(dashboard)/ops/OpsCenter.tsx"),
  // /ops/telemetry gộp thành tab "Sức khoẻ API" của /ops (18/09/2026);
  // /work-sessions chuyển hướng về /schedule (bảng work_session 0 dòng).
  opsPage: read("../app/(dashboard)/ops/page.tsx"),
  telemetry: read("../app/(dashboard)/ops/SucKhoeApi.tsx"),
  settings: read("../app/(dashboard)/settings/page.tsx"),
  // Bảng tài khoản nhân viên đã tách khỏi trang Cài đặt (06/08/2026). Bài kiểm
  // đi theo BẢNG, không đi theo đường dẫn cũ — nếu chỉ sửa `settings` cho hết
  // đỏ thì bảng dày kia không còn ai canh chiều rộng nữa.
  taiKhoan: read("../app/(dashboard)/settings/tai-khoan/page.tsx"),
  account: read("../app/(dashboard)/settings/AccountActions.tsx"),
  newUserPage: read("../app/(dashboard)/settings/new-user/page.tsx"),
  newUserForm: read("../app/(dashboard)/settings/new-user/NewUserForm.tsx"),
};

test("all operational and admin routes use the ClinicAI V2 page shell", () => {
  for (const key of [
    "lead",
    "schedule",
    "reports",
    "ops",
    "telemetry",
    "settings",
    "taiKhoan",
    "newUserPage",
  ] as const) {
    assert.match(sources[key], /page-in/,
      `${key} must opt into the V2 page shell`);
  }
});

// BÀI KIỂM CỦA MÀN TRƯỞNG CA CŨ ĐÃ GỠ (04/08/2026).
//
// Nó canh một bảng ĐỐI SOÁT: "Lượt khám hôm nay / Đã thanh toán / Cần theo dõi",
// đọc payRes + rxRes ngay trong trang. Màn đó đã được thay bằng BẢNG ĐIỀU PHỐI
// (ai đang ở phòng nào, chờ bao lâu, đi đâu tiếp) — không còn biến nào trong
// các assertion cũ tồn tại, nên chúng chỉ báo đỏ chứ không canh gì.
//
// Màn mới có bộ canh riêng: 18 bài test_dispatch_rules.py cho luật điều phối,
// luật chuyển phòng ở move_visit_to_station, và cổng vai ở roles.ts. Dòng
// aria-label của màn mới vẫn được canh ở ngay bài kiểm phía trên.
//
// 15 màn còn lại trong file này không đổi.

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
  for (const key of ["official", "register", "reports", "telemetry", "taiKhoan"] as const) {
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
  assert.match(sources.opsPage, /requireNavAccess\("\/ops"\)/);
  assert.match(sources.ops, /fetch\("\/api\/ops\/summary"/);
  assert.match(sources.register, /fetch\("\/api\/roster"/);
  assert.match(sources.account, /\/api\/admin\/users/);
  assert.match(sources.newUserForm, /\/api\/admin\/users/);
  assert.match(sources.settings, /isAdminRole\(role\)/);
  assert.match(sources.taiKhoan, /isAdminRole\(role\)/);
  assert.match(sources.reports, /isOpsAdmin\(role\)/);
});
