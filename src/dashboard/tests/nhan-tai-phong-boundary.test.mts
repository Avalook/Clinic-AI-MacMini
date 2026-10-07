// NHẬN KHÁCH TẠI PHÒNG — bố cục Tuyền chốt 07/10/2026 tối
// (docs/KE-HOACH-NHAN-TAI-PHONG.md):
//   * cột trái MỖI KHÁCH ĐÚNG MỘT DÒNG GỌN (3 chỉ định không trông như 3 người,
//     không vỡ chữ ở 375) — không liệt kê chỉ định trong danh sách;
//   * khung phải: chỉ định của khách, mỗi dòng MỘT nút theo trạng thái máy chủ
//     (Nhận / Bắt đầu / Xong) + "Nhận cả N"; KHÔNG tick sẵn, KHÔNG hộp tick;
//   * cùng phòng: 409 CUNG_PHONG_DANG_LAM → hỏi tại chỗ, nút "Xong … & bắt đầu …".
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");

const SAP_DEN = read("../app/(dashboard)/phong/[ma]/SapDenPhong.tsx");
const HANG = read("../app/(dashboard)/phong/[ma]/HangChoKhachPhong.tsx");
const KHUNG = read("../app/(dashboard)/phong/[ma]/KhungChiDinhKhach.tsx");
const NHAN = read("../app/(dashboard)/phong/[ma]/NhanChiDinh.tsx");
const PHONG = read("../app/(dashboard)/phong/[ma]/PhongDichVu.tsx");
const API = read("../app/(dashboard)/_lam-viec/api.ts");

test("danh sách bên trái: mỗi khách một dòng gọn, không liệt kê chỉ định", () => {
  for (const [ten, nd] of [
    ["SapDenPhong", SAP_DEN],
    ["HangChoKhachPhong", HANG],
  ] as const) {
    assert.doesNotMatch(nd, /chi_dinh\.map\(|cd\.map\(/, `${ten} không vẽ từng chỉ định thành dòng`);
    assert.doesNotMatch(nd, /<NhanChiDinh/, `${ten} không có nút Nhận trong danh sách`);
    // Một dòng: tên + dòng phụ đều cắt chữ (truncate), không xuống nhiều dòng ở 375.
    assert.match(nd, /truncate/);
    assert.match(nd, /chỉ định`/);
  }
});

test("bỏ tick sẵn: không còn tick_san / hộp tick", () => {
  for (const nd of [SAP_DEN, HANG, KHUNG, NHAN, API]) {
    assert.doesNotMatch(nd, /tick_san|co_tick_san|ChipChon/);
  }
});

test("khung phải: mỗi chỉ định một nút theo trạng thái + Nhận cả N", () => {
  assert.match(KHUNG, /ids=\{\[h\.id\]\}/, "Nhận trên dòng gửi đúng một id");
  assert.match(KHUNG, /Nhận cả \$\{nhanDuoc\.length\}/);
  assert.match(KHUNG, /"Bắt đầu"/);
  assert.match(KHUNG, /"Xong"/);
  // Trạng thái do máy chủ nói, màn không tự suy.
  assert.match(KHUNG, /c\.trang_thai === "cho"/);
  assert.match(KHUNG, /c\.trang_thai === "lam"/);
});

test("cùng phòng: hỏi tại chỗ, một nút Xong & bắt đầu, không tự Xong", () => {
  assert.match(PHONG, /CUNG_PHONG_DANG_LAM/);
  assert.match(PHONG, /xong_truoc: true/);
  assert.match(PHONG, /Xong \$\{hoiCungPhong\.dv\} & bắt đầu/);
  // Cờ chỉ gửi khi người bấm đồng ý (batDau(false, true) từ nút xác nhận).
  assert.match(PHONG, /onDongY=\{\(\) => batDau\(false, true\)\}/);
});

test("chuông nhận chéo mở đúng chỉ định qua ?chi_dinh=", () => {
  assert.match(PHONG, /get\("chi_dinh"\)/);
});
