import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");
const PANEL = "../app/(dashboard)/hoa-don/CongTyHoaDon.tsx";

test("hoá đơn công ty: route Next chỉ chuyển tiếp tới máy chủ, kiểm mã phiếu", () => {
  const phieu = read("../app/api/hoa-don/cong-ty/phieu/[id]/route.ts");
  for (const m of ["GET", "PUT", "DELETE"]) {
    assert.match(phieu, new RegExp(`export async function ${m}\\(`));
    assert.match(phieu, new RegExp(`proxyJsonToBackend\\("${m}", \`/api/v1/hoa-don/cong-ty/phieu/`));
  }
  assert.match(phieu, /UUID_RE\.test\(id\)/);
  assert.match(read("../app/api/hoa-don/cong-ty/phieu/[id]/lich-su/route.ts"), /\/lich-su/);
});

test("panel công ty gắn vào từng phiếu ở Chi tiết hoá đơn, không gắn vào phiếu đã huỷ", () => {
  const chiTiet = read("../app/(dashboard)/hoa-don/ChiTietHoaDon.tsx");
  assert.match(chiTiet, /import CongTyHoaDon from "\.\/CongTyHoaDon"/);
  assert.match(chiTiet, /<CongTyHoaDon paymentCycleId=\{p\.id\}/);
  assert.match(chiTiet, /DA_HUY/);
});

test("luật nằm ở máy chủ: panel không tự kiểm MST, không window.confirm, không cộng tiền", () => {
  const ui = read(PANEL);
  assert.doesNotMatch(ui, /\[0-9\]\{10\}|\\d\{10\}/); // MST chỉ nhắc: máy chủ trả canh_bao_mst
  assert.match(ui, /canh_bao_mst/);
  assert.doesNotMatch(ui, /window\.confirm|\.reduce\(/);
  assert.doesNotMatch(ui, /<button(?![^>]*type=)/);
  // Nhắc MST trung tính, không đỏ.
  assert.match(ui, /role="status"[^>]*text-ink-muted/);
  // 403 (không có quyền) → ẩn khối, không báo lỗi.
  assert.match(ui, /r\.status === 403/);
});

test("xem trước xuất hoá đơn: hoá đơn công ty hiện tên công ty, không hiện SĐT khách", () => {
  const ui = read("../app/(dashboard)/xuat-hoa-don/XuatHoaDon.tsx");
  assert.match(ui, /la_hd_cong_ty/);
  assert.match(ui, /ten_cong_ty/);
});
