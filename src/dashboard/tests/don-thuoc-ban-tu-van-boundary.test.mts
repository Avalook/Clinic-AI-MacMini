// Đơn thuốc điền tiếp ở BÀN TƯ VẤN (Tuyền 13/10/2026): bác sĩ chính điền dở /
// vội, bác sĩ tư vấn điền tiếp ĐÚNG đơn của lượt — không có đơn thứ hai, không
// luật nghiệp vụ trong TSX (quyền + người kê do máy chủ quyết).

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const doc = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");
const chiMa = (s: string) =>
  s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "").replace(/\{\/\*[\s\S]*?\*\/\}/g, "");

const BAN_TU_VAN = chiMa(doc("../app/(dashboard)/ban-kham/BanTuVan.tsx"));
const BAN_KHAM = chiMa(doc("../app/(dashboard)/ban-kham/BanKham.tsx"));
const KHOI = chiMa(doc("../app/(dashboard)/ban-kham/KhoiDonThuocBanTuVan.tsx"));
const DIEN_DON = chiMa(doc("../app/(dashboard)/ban-kham/BanDienDonThuoc.tsx"));
const PROXY = chiMa(doc("../lib/backend-proxy.ts"));
const PHIEU_LUOT = chiMa(doc("../app/(dashboard)/_lam-viec/phieu-kham/PhieuKhamLuot.tsx"));
const ROUTE = chiMa(doc("../app/api/phieu-kham/route.ts"));
const IN = chiMa(doc("../app/print/phieu-kham/[visitId]/InPhieuKham.tsx"));

test("khối Đơn thuốc dùng CHÍNH mục E của phiếu khám lượt (không form riêng)", () => {
  assert.match(KHOI, /<PhieuKhamLuot[\s\S]*chiMuc=\{\["E"\]\}/);
  assert.match(KHOI, /\/print\/phieu-kham\/\$\{visitId\}\?phan=don/, "in đơn tại bàn tư vấn");
  assert.doesNotMatch(KHOI, /fetch\(|guiThaoTac/, "TSX không tự ghi đơn");
});

test("bàn tư vấn: Xong tư vấn đợi cả đơn thuốc lưu xong", () => {
  assert.match(BAN_TU_VAN, /KhoiDonThuocBanTuVan/);
  assert.match(BAN_TU_VAN, /gopCong\(gopCong\(congTuVan, congPhieu\), congDon\)/);
});

test("khách đã khám xong (không qua tư vấn) có nhóm riêng ở bàn tư vấn", () => {
  assert.match(BAN_KHAM, /Đã khám xong — điền đơn thuốc/);
  assert.match(BAN_KHAM, /BanDienDonThuoc/);
  // Không có nút Hoàn tất / Mở lại khám của bác sĩ chính ở nhánh điền đơn.
  assert.doesNotMatch(DIEN_DON, /kham-xong|xong-tu-van|mo-lai-kham/);
  assert.match(DIEN_DON, /moSan/);
});

test("[Xong kê đơn thuốc] chỉ là mốc: đợi đơn lưu xong, có [Mở lại], đi qua một thao tác riêng", () => {
  assert.match(DIEN_DON, /thao_tac: "xong-ke-don"/);
  assert.match(DIEN_DON, /Xong kê đơn thuốc/);
  assert.match(DIEN_DON, /Mở lại/);
  assert.match(DIEN_DON, /cong\.luuNot/);
  assert.match(ROUTE, /thao_tac === "xong-ke-don"[\s\S]*ke-don-tu-van/);
  assert.match(BAN_KHAM, /Đã xong kê đơn thuốc/);
  assert.match(BAN_KHAM, /ke_don_tu_van_xong/);
});

test("sửa dòng đã thu tiền: màn tự ghi lý do mặc định, không bắt người kê gõ", () => {
  assert.match(PROXY, /ma_loi: maLoi/);
  assert.match(PHIEU_LUOT, /ma_loi === "PRESCRIPTION_CORRECTION_REASON_REQUIRED"/);
  assert.match(PHIEU_LUOT, /guiLan\(LY_DO_SUA_DON_DA_THU\)/);
  assert.doesNotMatch(PHIEU_LUOT, /Lưu đơn kèm lý do|aria-label="Lý do đính chính/);
});
test("phiếu in: ghi người kê theo từng dòng, in đơn riêng ký người ghi mới nhất", () => {
  assert.match(IN, /nguoiKeDon\(dl\.don\)/);
  assert.match(IN, /phan === "don" \? keDon\.nguoiKy : null/);
  assert.match(IN, /Người kê đơn:/);
});
