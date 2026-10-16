import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");

test("khối Dòng tiền dùng đúng chữ khách đưa, không còn nhãn cũ (14/10/2026)", () => {
  const ui = read("../app/(dashboard)/reports/TomTatCuoiNgay.tsx");
  for (const nhan of ["Dòng tiền", "Dòng tiền vào", "Trả lại tiền khách hàng", "Nợ thu được", "Thực thu", "Doanh thu thuần"]) {
    assert.match(ui, new RegExp(`"${nhan}"`));
  }
  assert.doesNotMatch(ui, /"Tài chính"|"Hoàn tiền mặt"|"Hoàn chuyển khoản"|Chưa có dữ liệu/);
  // Màn chỉ vẽ: số do máy chủ tính (dong_tien), không tự cộng trừ tiền.
  assert.match(ui, /dong_tien/);
  assert.doesNotMatch(ui, /\.reduce\(/);
});

test("mỗi mục có link sang danh sách hoá đơn giữ ngày / ca / cơ sở / nhóm", () => {
  const ui = read("../app/(dashboard)/reports/TomTatCuoiNgay.tsx");
  assert.match(ui, /\/hoa-don\?/);
  for (const nhom of ["tra_lai", "no_khach", "giam_gia", "khong_dung"]) assert.match(ui, new RegExp(`"${nhom}"`));
  const cuoiNgay = read("../app/(dashboard)/reports/CuoiNgay.tsx");
  assert.match(cuoiNgay, /loc=\{\{ tu: khoang\.tu, den: khoang\.den/);
  // Trang danh sách hoá đơn đọc bộ lọc từ link; route chuyển tiếp nhom + hinh_thuc.
  const page = read("../app/(dashboard)/hoa-don/page.tsx");
  assert.match(page, /searchParams: Promise/);
  assert.match(page, /banDau=\{banDau\}/);
  assert.match(read("../app/api/hoa-don/route.ts"), /"nhom", "hinh_thuc"/);
  const ds = read("../app/(dashboard)/hoa-don/DanhSachHoaDon.tsx");
  assert.match(ds, /dung_khong_dung/);
  assert.match(ds, /nhom, hinh_thuc: hinhThuc/);
});
