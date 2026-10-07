import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// Dịch vụ của lượt trong hồ sơ khám (Tuyền chốt 07/10/2026 — T1, T3, T5 của
// docs/KE-HOACH-CHON-DICH-VU-HO-SO-KHAM.md). Màn chỉ vẽ: đổi được không, vì sao,
// lịch sử, phiếu cũ, "Khách đã đặt" đều do máy chủ trả.
const doc = (f: string) => readFileSync(new URL(f, import.meta.url), "utf8");
const LUOT = doc("../app/(dashboard)/_lam-viec/phieu-kham/PhieuKhamLuot.tsx");
const KHOI = doc("../app/(dashboard)/_lam-viec/phieu-kham/KhoiDichVuHoSo.tsx");
const ROUTE = doc("../app/api/ho-so-kham/route.ts");

test("hồ sơ khám có khối Dịch vụ của lượt — cả phiếu đầy đủ lẫn hồ sơ tối giản", () => {
  assert.match(LUOT, /import KhoiDichVuHoSo from "\.\/KhoiDichVuHoSo"/);
  // Khối nằm ở đầu phiếu (dauTrang) VÀ ở nhánh không có phiếu (chonDuoc).
  assert.match(LUOT, /\{khoiDichVu\}\s*<HanhTrinhLuot/);
  const nhanhToiGian = LUOT.slice(LUOT.indexOf("if (chonDuoc) {"));
  assert.match(nhanhToiGian, /\{khoiDichVu\}/);
  assert.match(nhanhToiGian, /<DanhMucChiDinh/, "hồ sơ tối giản vẫn kê chỉ định được");
  assert.match(nhanhToiGian, /Ghi phiếu khám đầy đủ \(tuỳ chọn\)/);
  // Xem lại lượt cũ thì không có khối đổi dịch vụ.
  assert.match(LUOT, /xemLai \|\| chiMuc \? null/);
});

test("tính năng cũ của phiếu còn sống (tick dịch vụ khám, hành trình, in, chỉ định)", () => {
  assert.match(LUOT, /<ChonDichVuKham visitId=\{visitId\} \/>/);
  assert.match(LUOT, /<HanhTrinhLuot visitId=\{visitId\} \/>/);
  assert.match(LUOT, /\/print\/phieu-kham\/\$\{visitId\}/);
  assert.match(LUOT, /oChiDinhCls=\{/);
  assert.match(LUOT, /<LichSuSuaPhieu/);
});

test("khối dịch vụ: bộ chọn 4 nhóm dùng chung, không luật vai trong TSX", () => {
  assert.match(KHOI, /from "\.\.\/ChonDichVuDatLich"/);
  assert.match(KHOI, /\/api\/ho-so-kham/);
  assert.match(KHOI, /goi\.doi_duoc/);
  assert.match(KHOI, /ly_do_khong_doi/);
  assert.match(KHOI, /lich_su_doi/);
  assert.match(KHOI, /phieu_cu/);
  assert.match(KHOI, /khach_da_dat/);
  assert.doesNotMatch(KHOI, /DOCTOR|NURSE|TKYK|MANAGEMENT|isDoctor|role ===/);
});

test("route /api/ho-so-kham chỉ chuyển tiếp", () => {
  assert.match(ROUTE, /proxyJsonToBackend\("GET", `\/api\/v1\/ho-so-kham\/\$\{vid\}\/dich-vu`/);
  assert.match(ROUTE, /proxyJsonToBackend\("POST", `\/api\/v1\/ho-so-kham\/\$\{vid\}\/doi-dich-vu`/);
  assert.doesNotMatch(ROUTE, /\.from\(/, "không đọc thẳng database");
});
