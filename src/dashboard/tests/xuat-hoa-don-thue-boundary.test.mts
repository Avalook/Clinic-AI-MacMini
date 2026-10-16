import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");
const MAN = "../app/(dashboard)/xuat-hoa-don/XuatHoaDon.tsx";

test("route xuất hoá đơn chuyển thêm che_do, ghi_giam_gia, ghi_de (cho cả xem và tải Excel)", () => {
  const route = read("../app/api/xuat-hoa-don/route.ts");
  assert.match(route, /"che_do"/);
  assert.match(route, /"ghi_giam_gia"/);
  assert.match(route, /input\.get\("ghi_de"\)/);
  // Cùng chuỗi tham số cho xem trước và tải file → file khớp màn.
  assert.match(read(MAN), /\/api\/xuat-hoa-don\?\$\{chuoi\}&xuat=xlsx/);
});

test("màn xuất: chọn tách / một hoá đơn, công tắc ghi giảm giá, sửa tay thuế từng dòng", () => {
  const ui = read(MAN);
  assert.match(ui, /che_do: cheDo/);
  assert.match(ui, /thamSo\.set\("ghi_giam_gia", "true"\)/);
  assert.match(ui, /thamSo\.set\("ghi_de", JSON\.stringify\(ghiDe\)\)/);
  assert.match(ui, /Tách thành nhiều hoá đơn theo thuế suất/);
  assert.match(ui, /Ghi giảm giá trên hoá đơn/);
  assert.match(ui, /Sửa thuế suất dòng/);
  // Dòng chiết khấu (số âm) không có ô sửa thuế riêng.
  assert.match(ui, /d\.thanh_tien >= 0/);
  // Sửa tay chỉ áp cho lần xuất này và có lối bỏ hết.
  assert.match(ui, /chỉ áp cho lần xuất này/);
  assert.match(ui, /thuế sửa tay/);
});

test("luật thuế ở máy chủ: màn không tách thuế, không cộng tiền, chỉ đọc dong_chua_thue / tien_thue", () => {
  const ui = read(MAN);
  assert.match(ui, /data\.dong_chua_thue/);
  assert.match(ui, /h\.tien_thue/);
  assert.doesNotMatch(ui, /\.reduce\(|parseFloat|Math\.round|\* \(?1 \+/);
  assert.doesNotMatch(ui, /window\.confirm/);
  assert.doesNotMatch(ui, /<button(?![^>]*type=)/);
  // Chưa đặt thuế là việc cần làm, không phải lỗi: màu thông tin, có lối sang Kế toán.
  assert.match(ui, /dòng hàng chưa có thuế suất[\s\S]{0,200}href="\/ke-toan"/);
});
