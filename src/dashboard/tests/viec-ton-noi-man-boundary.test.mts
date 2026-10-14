import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");

// G4a nối màn (14/10/2026): bấm thật trên staging thấy việc tồn chỉ là thẻ chữ
// và link "Nợ" của báo cáo mở danh sách rỗng.

test("link Nợ của báo cáo mở thẳng tab Việc tồn đã lọc, không sang danh sách phiếu rỗng", () => {
  const ui = read("../app/(dashboard)/reports/TomTatCuoiNgay.tsx");
  assert.match(ui, /function linkViecTon/);
  assert.match(ui, /tab: "viec-ton", viec: nhom/);
  assert.match(ui, /href=\{linkViecTon\(loc, "no_khach"\)\}/);
  // Mục Nợ không còn đi theo `nhom=no_khach` (lượt ghi nợ chưa thu không có phiếu).
  assert.doesNotMatch(ui, /linkHoaDon\(loc, "no_khach"\)/);
});

test("/hoa-don đọc tab + viec từ URL và lọc việc tồn theo nhóm máy chủ gắn", () => {
  const page = read("../app/(dashboard)/hoa-don/page.tsx");
  assert.match(page, /tab: mot\("tab"\)/);
  assert.match(page, /viec: mot\("viec"\)/);
  const ds = read("../app/(dashboard)/hoa-don/DanhSachHoaDon.tsx");
  assert.match(ds, /banDau\.tab === "viec-ton" \? "ton" : "khach"/);
  assert.match(ds, /v\.nhom_no === viec \|\| v\.loai === viec/);
  // Đếm toàn cục lấy từ danh sách đầy đủ, không từ danh sách đã lọc.
  assert.match(ds, /dem: tonDay\.length/);
  assert.doesNotMatch(ds, /\.reduce\(/);
});

test("việc tồn có nút Xử lý do máy chủ quyết đích; thiếu lego thì chữ nhắc, không nút", () => {
  const ds = read("../app/(dashboard)/hoa-don/DanhSachHoaDon.tsx");
  assert.match(ds, /function NutXuLy/);
  assert.match(ds, /<NutXuLy v=\{v\} quyen=\{quyen\} \/>/);
  assert.match(ds, /coQuyen\(quyen, x\.lego\)/);
  assert.match(ds, /Nhờ người có quyền thu xử lý/);
  // Cả bảng desktop lẫn thẻ điện thoại đều có.
  assert.equal((ds.match(/<NutXuLy /g) ?? []).length, 2);
  // Màn không tự dựng link theo loại việc (luật nằm ở máy chủ).
  assert.doesNotMatch(ds, /\/thu-ngan\//);
});

test("quầy thu không lặng lẽ nhảy sang khách khác khi lượt của liên kết không có trong hàng chờ", () => {
  const quay = read("../app/(dashboard)/thu-ngan/QuayThuNgan.tsx");
  assert.match(quay, /const luotTuUrl = thamSo\?\.get\("luot"\) \?\? null/);
  assert.match(quay, /luotUrlLac/);
  assert.match(quay, /\(luotUrlLac \? null : \(conCho\[0\] \?\? null\)\)/);
  assert.match(quay, /Máy KHÔNG tự chọn khách khác/);
});

test("Check-out nhận ?luot= (UUID) và tô sáng đúng lượt tồn đọng", () => {
  const page = read("../app/(dashboard)/reception/checkout/page.tsx");
  assert.match(page, /UUID\.test\(sp\.luot\)/);
  assert.match(page, /luotMoSan=\{luot\}/);
  const board = read("../app/(dashboard)/reception/checkout/CheckoutBoard.tsx");
  assert.match(board, /luotNoiBat=\{luotMoSan\}/);
  const ton = read("../app/(dashboard)/reception/checkout/LuotTonDong.tsx");
  assert.match(ton, /luotNoiBat === l\.visit_id/);
  assert.match(ton, /scrollIntoView/);
});
