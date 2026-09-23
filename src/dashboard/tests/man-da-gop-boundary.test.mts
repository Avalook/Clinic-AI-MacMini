// MÀN ĐÃ GỘP CHỈ CÒN CHUYỂN HƯỚNG (Tuyền chốt 18/09/2026 — docs/SITEMAP.md).
//
// Bài học 17/09: nút QR được gỡ ở màn thu ngân CŨ (/tasks) trong khi màn thật
// là /thu-ngan/*. Màn cũ còn sống là chỗ để sửa nhầm. Bài kiểm này giữ cho
// chúng chết hẳn: file trang chỉ còn redirect, không mục thanh bên, không dòng
// quyền trong NAV_ROLES.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { canSeeNavGoc, roleLanding } from "../lib/roles.ts";

const read = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");

const DA_GOP: Record<string, string> = {
  "tasks": "", // chuyển theo vai — kiểm riêng bên dưới
  "queue": "/reception/queue",
  "cashier/board": "/thu-ngan/dich-vu",
  "cskh-tasks": "/customers",
  "episodes": "/customers",
  "work-sessions": "/schedule",
  "portal": "/ops?tab=toan-canh",
  "ops/telemetry": "/ops?tab=api",
};

test("mỗi màn đã gộp chỉ còn redirect, không giao diện, không cửa quyền", () => {
  for (const [duong, dich] of Object.entries(DA_GOP)) {
    const src = read(`../app/(dashboard)/${duong}/page.tsx`);
    assert.match(src, /redirect\(/, `/${duong} phải chuyển hướng`);
    assert.doesNotMatch(src, /requireNavAccess|return\s*\(|<[A-Z]/, `/${duong} còn giao diện`);
    if (dich) assert.ok(src.includes(`redirect("${dich}")`), `/${duong} phải về ${dich}`);
  }
});

test("thanh bên và NAV_ROLES không còn trỏ vào màn đã gộp", () => {
  // nav-items.ts không nạp được dưới node --test (import không đuôi), nên
  // đọc như văn bản — cùng cách các bài kiểm thanh bên khác làm.
  const nav = read("../app/(dashboard)/nav-items.ts");
  const roles = read("../lib/roles.ts");
  for (const duong of Object.keys(DA_GOP)) {
    assert.ok(!nav.includes(`href: "/${duong}"`), `thanh bên còn mục /${duong}`);
    assert.ok(!roles.includes(`  "/${duong}": `), `NAV_ROLES còn dòng /${duong}`);
  }
});

test("/tasks đưa từng vai về màn chuẩn của vai ấy", () => {
  const src = read("../app/(dashboard)/tasks/page.tsx");
  // Đích tuỳ vai ⇒ trang phải động, không thì build đông cứng vai null → /home.
  assert.match(src, /export const dynamic = "force-dynamic"/);
  for (const dich of ["/thu-ngan/dich-vu", "/phong", "/ban-kham", "/do-sinh-hieu", "/reception/queue", "/customers"]) {
    assert.ok(src.includes(`redirect("${dich}")`), `/tasks thiếu nhánh về ${dich}`);
  }
});

test("đăng nhập xong không ai bị đưa về màn cũ", () => {
  // Trang gốc chuyển theo vai ⇒ phải động (bản build 18/09 báo ○ Static:
  // mọi người mở "/" đều về /home).
  assert.match(read("../app/page.tsx"), /export const dynamic = "force-dynamic"/);
  assert.equal(roleLanding("DOCTOR"), "/ban-kham");
  assert.equal(roleLanding("TKYK"), "/ban-kham");
  // Không còn mã phòng viết cứng (CORE-C): vào danh sách phòng rồi chọn.
  assert.equal(roleLanding("ULTRASOUND_DOCTOR"), "/phong");
  // Và nơi đến phải là nơi vai ấy được vào theo luật gốc.
  assert.equal(canSeeNavGoc("DOCTOR", "/ban-kham"), true);
  assert.equal(canSeeNavGoc("TKYK", "/ban-kham"), true);
  assert.equal(canSeeNavGoc("ULTRASOUND_DOCTOR", "/phong"), true);
});

test("thông báo kết quả về trỏ thẳng màn Duyệt kết quả, không qua đường cũ", () => {
  const py = read("../../clinicai/services/bao_ket_qua_ve.py");
  assert.doesNotMatch(py, /\/result-review/);
  assert.match(py, /duong_dan="\/duyet-ket-qua"/);
});

test("check-in chỉ ở Tiếp đón khách — Trang chủ không bật cột check-in", () => {
  const home = read("../app/(dashboard)/home/page.tsx");
  assert.doesNotMatch(home, /choCheckIn/);
  assert.doesNotMatch(home, /HomeCheckin/);
  const quay = read("../app/(dashboard)/reception/queue/page.tsx");
  assert.match(quay, /choCheckIn/);
  const bang = read("../app/(dashboard)/home/WeeklyAppointmentsTable.tsx");
  assert.match(bang, /const showActions = choCheckIn && canCheckin\(role\)/);
});

test("nhóm màn đăng nhập không được dựng tĩnh — đường chuyển hướng không được đông cứng về /login", () => {
  // Đo trên prod 18/09/2026: thiếu dòng này thì mọi trang chỉ-chuyển-hướng bị
  // dựng lúc không có phiên, và người đã đăng nhập bấm vào là về /login.
  assert.match(
    read("../app/(dashboard)/layout.tsx"),
    /export const dynamic = "force-dynamic"/,
  );
});
