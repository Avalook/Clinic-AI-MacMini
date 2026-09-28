import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";

// CỬA QUYỀN THEO LEGO — so BA nơi (kiểm toán 27/09/2026).
//
//   1. Danh mục lego   `MAN` trong src/clinicai/permissions/catalogue.py
//   2. Thanh bên       `NAV` + `NAV_QUYEN` (nav-items.ts, lib/roles.ts)
//   3. Cửa trang       `requireNavAccess(...)` trong từng page.tsx → `vaoDuocMan`
//
// Trước bài này không gì so ba nơi, và chúng lệch hai chiều: gõ thẳng URL vào
// được màn thuộc lego đang TẮT (16 ô khi quét màn × tài khoản), còn 8 trang
// gác bằng VAI nên cấp lego rồi vẫn bị đá về /home.

import {
  GIU_LOI_VAO_CU,
  laManLego,
  legoChoHien,
  quyenMoDuocMan,
  vaoDuocMan,
  type ClinicRole,
} from "../lib/roles.ts";

const doc = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");

// ── 1. Đọc danh mục lego từ Python ─────────────────────────────────────────
const catalogue = doc("../../clinicai/permissions/catalogue.py");
const khoiMan = catalogue.slice(
  catalogue.indexOf("MAN: dict[str, Man] = {"),
  catalogue.indexOf("LUON_BAT:"),
);
const LEGO = new Map<string, string[]>(
  [...khoiMan.matchAll(/_lego\(\s*"(\w+)",\s*"[^"]*",\s*\[([^\]]*)\]/g)].map((m) => [
    m[1],
    [...m[2].matchAll(/"(\/[^"]*)"/g)].map((x) => x[1]),
  ]),
);
const DUONG_LEGO = [...LEGO.values()].flat();
const QUYEN_DA_KHAI = new Set(
  [...catalogue.matchAll(/Quyen\(\s*"([a-z_.]+)"/g)].map((m) => m[1]),
);

const roles = doc("../lib/roles.ts");
const khoiNavQuyen = roles.slice(
  roles.indexOf("const NAV_QUYEN"),
  roles.indexOf("const TAT_KHOI_THANH_BEN"),
);
const NAV_QUYEN_CAP = [...khoiNavQuyen.matchAll(/"([a-z_]+\.[a-z_.]+)"/g)].map((m) => m[1]);

const nav = doc("../app/(dashboard)/nav-items.ts");
const HREF_THANH_BEN = new Set(
  [...nav.matchAll(/href:\s*"(\/[a-z0-9/-]*)"/g)].map((m) => m[1]),
);

/** page.tsx của một đường dẫn — trong nhóm (dashboard) hoặc ngoài (đối tác). */
function trangCua(duong: string): string | null {
  for (const p of [`../app/(dashboard)${duong}/page.tsx`, `../app${duong}/page.tsx`]) {
    const url = new URL(p, import.meta.url);
    if (existsSync(url)) return readFileSync(url, "utf8");
  }
  return null;
}

test("bộ đọc danh mục còn sống (chống xanh giả)", () => {
  assert.equal(LEGO.size, 21, `đọc được ${LEGO.size} lego, danh mục chốt 21`);
  assert.ok(DUONG_LEGO.length >= 30, `chỉ đọc được ${DUONG_LEGO.length} màn lego`);
  assert.ok(QUYEN_DA_KHAI.size >= 40);
});

test("mọi màn lego đều có quyền mở trong NAV_QUYEN — thiếu là cửa rơi về vai", () => {
  const thieu = DUONG_LEGO.filter((d) => !laManLego(d));
  assert.deepEqual(thieu, [], `màn lego không có dòng NAV_QUYEN: ${thieu.join(", ")}`);
});

test("quyền trong NAV_QUYEN đều có thật trong danh mục backend", () => {
  const ma = NAV_QUYEN_CAP.filter((q) => !QUYEN_DA_KHAI.has(q));
  assert.deepEqual(ma, [], `quyền không có trong catalogue.py: ${ma.join(", ")}`);
});

test("mọi màn lego đều có trên thanh bên (trừ màn mở từ màn khác)", () => {
  // /settings/new-user mở từ nút ở /settings/tai-khoan, không có mục riêng.
  const MO_TU_MAN_KHAC = new Set(["/settings/new-user"]);
  const thieu = DUONG_LEGO.filter((d) => !HREF_THANH_BEN.has(d) && !MO_TU_MAN_KHAC.has(d));
  assert.deepEqual(thieu, [], `màn lego không có trên thanh bên: ${thieu.join(", ")}`);
});

test("mọi trang lego gác bằng requireNavAccess(đúng đường của nó), không gác bằng vai", () => {
  const hong: string[] = [];
  for (const d of DUONG_LEGO) {
    const src = trangCua(d);
    if (src === null) {
      hong.push(`${d}: không có page.tsx`);
      continue;
    }
    if (!src.includes(`requireNavAccess("${d}")`)) {
      hong.push(`${d}: thiếu requireNavAccess("${d}")`);
    }
    // Cửa vai kiểu cũ: `if (!isOpsAdmin(role)) redirect(...)`.
    if (/if \(!\s*(is[A-Z]\w*|can[A-Z]\w*)\(role\)\)\s*redirect/.test(src)) {
      hong.push(`${d}: còn cửa theo vai`);
    }
  }
  assert.deepEqual(hong, []);
});

test("màn theo phòng dùng cửa lego của màn gốc", () => {
  assert.match(trangCua("/phong/[ma]") ?? "", /requireNavAccess\(`\/phong\/\$\{ma\}`\)/);
  assert.match(
    trangCua("/ban-kham/[phong]") ?? "",
    /requireNavAccess\(`\/ban-kham\/\$\{phong\}`\)/,
  );
});

// ── 2. Chiều LỌT: 16 ô của lần quét 27/09 — lego TẮT thì URL cũng đóng ─────
//
// Vai ở đây là VAI HIỆU LỰC hôm ấy (gồm vai suy từ lego khác), quyền là đủ bộ
// quyền của các lego đang bật TRỪ lego của màn đang thử.
const PHONG = "/phong/5f0c7a2e-0000-4000-8000-000000000001";
const O_LOT: [string, ClinicRole[], string[]][] = [
  // letan: lego Đo sinh hiệu → vai ĐD; lego CSKH → vai CSKH.
  ["/phong", ["RECEPTION", "NURSE_ULTRASOUND", "CSKH"], ["vitals.measure", "crm.manage"]],
  [PHONG, ["RECEPTION", "NURSE_ULTRASOUND", "CSKH"], ["vitals.measure", "crm.manage"]],
  ["/audit-log", ["RECEPTION", "CSKH"], ["crm.manage", "reception.checkin.perform"]],
  // thungan: vai CSKH suy từ lego Chăm sóc khách.
  ["/audit-log", ["CASHIER", "CSKH"], ["crm.manage", "payment.service.collect"]],
  ["/appointments", ["CASHIER", "CSKH"], ["crm.manage", "payment.service.collect"]],
  ["/patients/new", ["CASHIER", "CSKH"], ["crm.manage", "payment.service.collect"]],
  // bs.a
  ["/do-sinh-hieu", ["DOCTOR"], ["clinical.consult.perform"]],
  // truongca
  ["/do-sinh-hieu", ["TRUONG_CA"], ["dispatch.manage"]],
  ["/thu-ngan/thuoc", ["TRUONG_CA"], ["dispatch.manage"]],
  ["/settings/booking-policy", ["TRUONG_CA"], ["dispatch.manage", "report.view"]],
  // dd.sa
  ["/reception/queue", ["NURSE_ULTRASOUND"], ["vitals.measure"]],
  // danang: vai Lễ tân theo lịch.
  ["/appointments", ["RECEPTION"], ["reception.checkin.perform"]],
  ["/customers", ["RECEPTION"], ["reception.checkin.perform"]],
  ["/pharmacy", ["RECEPTION"], ["reception.checkin.perform"]],
  ["/pharmacy/inventory", ["RECEPTION"], ["reception.checkin.perform"]],
  ["/cashier/dich-vu", ["RECEPTION"], ["reception.checkin.perform"]],
  ["/patients/new", ["RECEPTION"], ["reception.checkin.perform"]],
  ["/thu-ngan/thuoc", ["RECEPTION"], ["reception.checkin.perform"]],
];

test("chiều LỌT: màn thuộc lego đang tắt thì gõ URL cũng không vào", () => {
  // Trừ đúng các cặp GIỮ LỐI VÀO CŨ (ngoại lệ tạm có đếm prod, chờ Tuyền chốt).
  const giu = (href: string, vai: ClinicRole[]) =>
    vai.some((r) => (GIU_LOI_VAO_CU[href] ?? []).includes(r));
  const lot = O_LOT.filter(
    ([href, vai, quyen]) => vaoDuocMan(href, vai, quyen) && !giu(href, vai),
  ).map(([href, vai]) => `${vai[0]} → ${href}`);
  assert.deepEqual(lot, [], `còn lọt: ${lot.join(" · ")}`);
});

test("ngoại lệ giữ lối vào cũ: ĐÃ BỎ — chỉ dùng lego (Tuyền 27/09, đợt 3)", () => {
  // Ba cặp cũ (BS/lễ tân → Đo sinh hiệu, ĐD → Tiếp đón) chỉ vì cửa theo vai;
  // máy chủ đã hỏi lego ở lệnh. Cần thì bật lego ở /phan-quyen.
  assert.deepEqual(Object.keys(GIU_LOI_VAO_CU), []);
  assert.equal(vaoDuocMan("/reception/queue", ["NURSE_ULTRASOUND"], ["vitals.measure"]), false);
  assert.equal(vaoDuocMan("/do-sinh-hieu", ["DOCTOR"], ["clinical.consult.perform"]), false);
  assert.equal(vaoDuocMan("/do-sinh-hieu", ["DOCTOR"], ["vitals.measure"]), true);
  assert.equal(
    vaoDuocMan("/reception/queue", ["NURSE_ULTRASOUND"], ["reception.checkin.perform"]),
    true,
  );
  assert.equal(vaoDuocMan("/phong", ["RECEPTION"], ["reception.checkin.perform"]), false);
});

// ── 3. Chiều CHẶN NHẦM: cấp lego là vào được, bất kể vai ───────────────────
const O_CHAN_NHAM: [string, ClinicRole[], string[]][] = [
  ["/reports", ["RECEPTION"], ["report.view"]],
  ["/lich-do-ve", ["CSKH"], ["report.view"]],
  ["/settings", ["TRUONG_CA"], ["config.clinic.manage"]],
  ["/settings/booking-policy", ["CSKH"], ["config.clinic.manage"]],
  ["/settings/tai-khoan", ["TRUONG_CA"], ["account.manage"]],
  ["/settings/new-user", ["TRUONG_CA"], ["account.manage"]],
  ["/patients/new", ["CASHIER"], ["patient.create"]],
  ["/schedule", ["CSKH"], ["roster.view"]],
  ["/doi-tac", ["NURSE_ULTRASOUND"], ["partner.work"]],
  ["/phong", ["RECEPTION"], ["service.execute.start"]],
  [PHONG, ["RECEPTION"], ["service.execute.start"]],
];

test("chiều CHẶN NHẦM: cấp lego thì vào được, không cần vai", () => {
  const chan = O_CHAN_NHAM.filter(([href, vai, quyen]) => !vaoDuocMan(href, vai, quyen)).map(
    ([href, vai]) => `${vai[0]} → ${href}`,
  );
  assert.deepEqual(chan, [], `còn chặn nhầm: ${chan.join(" · ")}`);
});

test("Quản lý KHÔNG có đường vòng: thu lego là mất màn (mô hình quyền không có ngoại lệ)", () => {
  assert.equal(vaoDuocMan("/settings", ["MANAGEMENT"], []), false);
  assert.equal(vaoDuocMan("/settings", ["MANAGEMENT"], ["config.clinic.manage"]), true);
});

test("máy chủ chưa trả lời quyền (null) → luật vai gốc, không khoá cả phòng khám", () => {
  assert.equal(vaoDuocMan("/ban-kham", ["DOCTOR"], null), true);
  assert.equal(vaoDuocMan("/settings", ["DOCTOR"], null), false);
  // Tài khoản đối tác: /phan-quyen/toi từ chối vai này → null → vẫn vào màn mình.
  assert.equal(vaoDuocMan("/doi-tac", ["PARTNER"], null), true);
  assert.equal(vaoDuocMan("/ban-kham", ["PARTNER"], null), false);
});

test("màn KHÔNG thuộc lego giữ luật vai cũ", () => {
  assert.equal(laManLego("/home"), false);
  assert.equal(laManLego("/hanh-trinh"), false);
  assert.equal(vaoDuocMan("/home", ["RECEPTION"], []), true);
  assert.equal(vaoDuocMan("/hanh-trinh", ["RECEPTION"], []), true);
  assert.equal(vaoDuocMan("/hanh-trinh", ["PARTNER"], null), false);
});

// ── 4. Thanh bên ngày có ca: vị trí quyết màn nào bày, lego quyết được bày ──
test("thanh bên theo vị trí lọc qua lego", () => {
  assert.equal(legoChoHien(["vitals.measure"], "/reception/queue"), false);
  assert.equal(legoChoHien(["reception.checkin.perform"], "/reception/queue"), true);
  assert.equal(legoChoHien(null, "/reception/queue"), true, "chưa biết quyền → không lọc");
  assert.equal(legoChoHien([], "/home"), true, "màn ngoài lego luôn bày");
  assert.equal(quyenMoDuocMan(["service.execute.start"], PHONG), true);

  const i = nav.indexOf("export function mucHienRa");
  const than = nav.slice(i, nav.indexOf("export function nhomThanhBen"));
  assert.match(than, /\.filter\(\(h\) => legoChoHien\(quyen, h\)\)/);
  const j = nav.indexOf("export function nhomThanhBen");
  const than2 = nav.slice(j, j + 2400);
  assert.match(than2, /viTriHomNay, phong, quyen,/);
  assert.match(than2, /legoChoHien\(quyen, "\/schedule"\)/);
  for (const f of ["../app/(dashboard)/Nav.tsx", "../app/(dashboard)/BottomNav.tsx"]) {
    assert.match(doc(f), /phong,\s*\/\/[^\n]*\n\s*quyen,\s*\);/, `${f} phải truyền quyền`);
  }
});

// ── 5. Proxy Next không tự gác bằng vai — backend quyết ────────────────────
test("proxy đang sống chỉ kiểm đăng nhập, không gác bằng vai", () => {
  const PROXY = [
    "booking-overrides/doctor/[id]/route.ts",
    "booking-overrides/slot/[id]/route.ts",
    "booking-rules/route.ts",
    "cskh-action/route.ts",
    "dispatch/[action]/route.ts",
    "lab-result/[id]/review/route.ts",
    "lab-result/[id]/triage/route.ts",
    "patients/check-duplicate/route.ts",
    "patients/route.ts",
    "patients/sdt-them/route.ts",
    "recall-jobs/[id]/ket-qua/route.ts",
    "reception/checkout/route.ts",
    "roster/route.ts",
  ];
  const hong: string[] = [];
  for (const p of PROXY) {
    // Bỏ chú thích: lời giải thích "cửa vai cũ đã bỏ" không phải cửa vai.
    const src = doc(`../app/api/${p}`).replace(/\/\/[^\n]*/g, "");
    if (!/auth\.getUser\(\)/.test(src)) hong.push(`${p}: không kiểm đăng nhập`);
    if (/vaiLamViec|getVaiHomNay|is[A-Z]\w*Role\(|canWriteIntake|canEditPatient/.test(src)) {
      hong.push(`${p}: còn cửa vai`);
    }
  }
  assert.deepEqual(hong, []);
});

test("công tắc mở quyền tạm thời: thiếu biến thì TẮT (hỏng thì đóng)", () => {
  assert.match(roles, /NEXT_PUBLIC_MO_QUYEN_TAM_THOI \?\? "0"/);
  assert.match(doc("../Dockerfile.dashboard"), /ARG NEXT_PUBLIC_MO_QUYEN_TAM_THOI=0/);
  assert.match(doc("../../../docker-compose.yml"), /\$\{MO_QUYEN_TAM_THOI:-0\}/);
});
