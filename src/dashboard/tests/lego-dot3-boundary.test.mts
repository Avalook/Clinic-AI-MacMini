// ĐỢT 3 (27/09/2026) — "thừa thiếu nút như ở bác sĩ tư vấn": nút, cửa trang và
// thanh bên theo LEGO của tài khoản, không theo vai. Luật quyền thật ở máy chủ
// (`permissions/doc_bang.py`, `cua_noi_bo`); ở đây canh phần giao diện.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  ALL_ROLES,
  canSeeNav,
  luonBatChoVaiGoc,
  nutBanKham,
  vaoDuocMan,
  type ClinicRole,
} from "../lib/roles.ts";

const doc = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");
const boChuThich = (s: string) =>
  s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/[^\n]*/g, "$1");

test("nút Bàn khám / tư vấn theo LEGO, không theo vai", () => {
  // Tài khoản ĐD bật đủ lego Bàn khám: có khám + hoàn tất.
  assert.deepEqual(
    nutBanKham(["clinical.consult.perform", "clinical.consult.finalize"], "NURSE_ULTRASOUND"),
    { kham: true, hoanTat: true, tuVan: false },
  );
  // Thư ký (Bàn khám thiếu Hoàn tất) — khám được, chờ bác sĩ hoàn tất.
  assert.deepEqual(nutBanKham(["clinical.consult.perform"], "TKYK"), {
    kham: true,
    hoanTat: false,
    tuVan: false,
  });
  // Bác sĩ CHỈ bật lego Khám tư vấn: chỉ nút tư vấn.
  assert.deepEqual(nutBanKham(["clinical.intake.perform"], "DOCTOR"), {
    kham: false,
    hoanTat: false,
    tuVan: true,
  });
  // Bác sĩ tắt hết lego khám → không nút nào, dù vai là Bác sĩ.
  assert.deepEqual(nutBanKham([], "DOCTOR"), { kham: false, hoanTat: false, tuVan: false });
  // Máy chủ im (null) → rơi về vai, không mất hết nút vì một lần lỗi mạng.
  assert.deepEqual(nutBanKham(null, "DOCTOR"), { kham: true, hoanTat: true, tuVan: true });
  assert.deepEqual(nutBanKham(null, "TKYK"), { kham: true, hoanTat: false, tuVan: false });
  assert.deepEqual(nutBanKham(null, null), { kham: false, hoanTat: false, tuVan: false });
});

test("BanKham không còn hỏi vai; ba trang truyền `nut` từ getNutBanKham", () => {
  const ban = boChuThich(doc("../app/(dashboard)/ban-kham/BanKham.tsx"));
  assert.doesNotMatch(ban, /vai === "DOCTOR"|vai === "TKYK"/);
  assert.match(ban, /const laBacSi = nut\.hoanTat;/);
  assert.match(ban, /const choBam = tuVan \? nut\.tuVan : nut\.kham;/);
  assert.match(ban, /!tuVan && nut\.kham \? \(\s*<ChoBacSiQuyet/);
  for (const p of [
    "../app/(dashboard)/ban-kham/page.tsx",
    "../app/(dashboard)/ban-kham/[phong]/page.tsx",
    "../app/(dashboard)/tu-van/page.tsx",
  ]) {
    const src = doc(p);
    assert.match(src, /await getNutBanKham\(\)/, p);
    assert.match(src, /nut=\{nut\}/, p);
    assert.doesNotMatch(src, /vaiLamViec/, p);
  }
});

test("Hành trình LUÔN BẬT cho mọi vai TÀI KHOẢN nội bộ, kể cả khi lego mang vai tắt", () => {
  const noiBo = ALL_ROLES.filter((r) => r !== "PARTNER" && r !== "DISPLAY");
  for (const r of noiBo) {
    assert.equal(canSeeNav(r, "/hanh-trinh"), true, r);
    assert.equal(luonBatChoVaiGoc("/hanh-trinh", r), true, r);
  }
  for (const r of ["PARTNER", "DISPLAY"] as ClinicRole[]) {
    assert.equal(canSeeNav(r, "/hanh-trinh"), false, r);
    assert.equal(luonBatChoVaiGoc("/hanh-trinh", r), false, r);
  }
  assert.equal(luonBatChoVaiGoc("/hanh-trinh", null), false);
  // Không phải màn luôn bật → không mở theo vai gốc.
  assert.equal(luonBatChoVaiGoc("/ban-kham", "DOCTOR"), false);
  // Lễ tân tắt lego Tiếp đón (vai hôm nay rỗng): luật lego một mình thì đóng…
  assert.equal(vaoDuocMan("/hanh-trinh", [], []), false);
  // …nên cửa trang hỏi thêm vai tài khoản.
  const phien = doc("../lib/clinic-session.ts");
  assert.match(
    phien,
    /return vaoDuocMan\(href, vai, quyen\) \|\| luonBatChoVaiGoc\(href, await getClinicRole\(\)\);/,
  );
  // Layout không còn hiện trang lỗi khi vai hôm nay rỗng.
  assert.match(phien, /export const getVaiHienThi = cache\(/);
  assert.match(doc("../app/(dashboard)/layout.tsx"), /await getVaiHienThi\(\)/);
});

test("thanh bên ngày có ca: Hành trình cạnh Trang chủ, nhóm lego mở sẵn, gập được", () => {
  const nav = doc("../app/(dashboard)/nav-items.ts");
  const i = nav.indexOf("export function nhomThanhBen");
  const than = nav.slice(i);
  assert.match(than, /i\.href === "\/hanh-trinh"/);
  assert.match(than, /lego: conLai\.filter\(dangBat\)/);
  assert.match(than, /laManLego\(i\.href\) && quyenMoDuocMan\(quyen, i\.href\)/);
  const navTsx = doc("../app/(dashboard)/Nav.tsx");
  // 28/09/2026 (Tuyền): nhóm lego là nhóm RIÊNG, không chữ (chỉ mũi tên), MỌI
  // nhóm gập được — không còn nhánh `coGap = false`, không còn ép mở nhóm đang
  // đứng (chỉ tự mở một lần khi tới trang).
  assert.match(navTsx, /lego: lego0/);
  assert.match(navTsx, /\{ ma: "lego-dang-bat", ten: "", muc: lego \}/);
  assert.doesNotMatch(navTsx, /coGap/);
  assert.match(navTsx, /const mo = isCollapsed \|\| !gap\.includes\(g\.ma\)/);
});

test("Việc cần xử lý: lỗi hiện rõ, tên khách đúng trường, mã node thật, có Xem lượt", () => {
  const bang = doc("../app/(dashboard)/viec-can-xu-ly/BangViecCanXuLy.tsx");
  const ma = boChuThich(bang);
  // Lần nạp đầu lỗi → không đứng "Đang tải…" mãi.
  assert.match(ma, /if \(ds === null\) \{\s*return loi \? \(/);
  // Trường khớp `WorklistPatient` ở routers/work_items.py.
  assert.match(ma, /v\.patient\?\.full_name/);
  assert.match(ma, /v\.patient\?\.patient_code/);
  assert.doesNotMatch(ma, /patient\?\.ten\b|patient\?\.ma_bn/);
  // Mã node THẬT (migration 20260923000007), không mã tự đặt.
  for (const m of ["OPS-FINANCIAL-RESOLUTION", "OPS-SERVICE-INTERRUPTED", "OPS-ROUTING-REASSIGN"]) {
    assert.match(ma, new RegExp(`"${m}"`), m);
  }
  assert.doesNotMatch(ma, /OPS-DOI-SOAT-TIEN|OPS-QUYET-LAM-LAI/);
  assert.match(ma, /<NutXemLuot visitId=\{v\.visit_id\}/);
  // "Đã xử lý" từ PENDING: start trước, rồi complete.
  assert.match(ma, /v\.status === "PENDING"[\s\S]*?lenh\(v\.id, "start"[\s\S]*?lenh\(v\.id, "complete"/);
  // Trống → câu "không có việc".
  assert.match(ma, /Không có việc nào đang chờ/);
  const trang = boChuThich(doc("../app/(dashboard)/viec-can-xu-ly/page.tsx"));
  assert.doesNotMatch(trang, /<main|<h1/);
});
