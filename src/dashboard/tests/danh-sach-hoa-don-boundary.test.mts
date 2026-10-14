import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");
test("Danh sách hoá đơn đứng ngay dưới Báo cáo và dùng cửa report.view", () => {
  const nav = read("../app/(dashboard)/nav-items.ts");
  assert.match(nav, /href: "\/reports", label: "Báo cáo"[^\n]+\n\s*\{ href: "\/hoa-don", label: "Danh sách hoá đơn"/);
  assert.match(read("../lib/roles.ts"), /"\/hoa-don": \["report.view"\]/);
});
test("hai quầy cùng tạo bill, vẫn giữ xác minh tiền chuyển khoản", () => {
  const quay = read("../app/(dashboard)/thu-ngan/QuayThuNgan.tsx");
  assert.match(quay, /"Tạo bill"/);
  // Xác minh gửi kèm số ngân hàng thật nhận (G4d, R1) — tuỳ chọn, trống = null.
  assert.match(quay, /onXacMinh\(ma\.trim\(\), soNhan === "" \? null : Number\(soNhan\)\)/);
  for (const p of ["dich-vu", "thuoc"]) assert.match(read(`../app/(dashboard)/thu-ngan/${p}/page.tsx`), /Tạo bill/);
  // Quầy dịch vụ (hoá đơn từng lượt) cùng chữ với quầy thuốc — không còn nút "Thu" (13/10/2026).
  const hoaDon = read("../app/(dashboard)/thu-ngan/HoaDonMot.tsx");
  assert.match(hoaDon, /"Tạo bill"/);
  assert.doesNotMatch(hoaDon, /: "Thu"\}/);
});
test("UI nhận số tiền từ backend và có popup chi tiết chứng từ", () => {
  const ui = read("../app/(dashboard)/hoa-don/DanhSachHoaDon.tsx");
  assert.match(ui, /\/api\/hoa-don/);
  assert.match(ui, /AbortController/);
  assert.match(ui, /da_thu/); assert.match(ui, /da_hoan/); assert.match(ui, /cho_hoan/); assert.match(ui, /chua_tra_lai/); assert.match(ui, /tong_khach/); assert.match(ui, /thu_rong/);
  assert.doesNotMatch(ui, /\.reduce\(/);
  const detail = read("../app/(dashboard)/hoa-don/ChiTietHoaDon.tsx");
  assert.match(detail, /HopChiTiet/); assert.match(detail, /nguoi_thu/); assert.match(detail, /su_kien/); assert.match(detail, /ly_do/); // lý do huỷ nằm trong "Sau khi thu" (v8)
});
