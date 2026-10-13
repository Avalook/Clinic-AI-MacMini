import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (file: string) => readFileSync(new URL(file, import.meta.url), "utf8");
test("Giảm giá hiển thị ở bảng khách và thẻ di động, số tiền lấy từ máy chủ", () => {
  const list = read("../app/(dashboard)/hoa-don/DanhSachHoaDon.tsx");
  assert.match(list, /"Giảm giá"/);
  assert.match(list, /k\.giam_gia/);
  assert.doesNotMatch(list, /\.reduce\(/);
});
test("popup phân biệt tiền trước giảm và thực thu, lý do người giờ giảm", () => {
  const detail = read("../app/(dashboard)/hoa-don/ChiTietHoaDon.tsx");
  for (const field of ["tong_truoc_giam", "giam_gia", "ly_do_giam", "nguoi_giam", "giam_luc", "thanh_tien_truoc_giam"]) assert.match(detail, new RegExp(field));
  assert.match(detail, /tien\(p\.so_tien\)/);
  assert.doesNotMatch(detail, /p\.so_tien\s*\|\|/);
});
