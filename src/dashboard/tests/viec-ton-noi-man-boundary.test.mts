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
  assert.match(ds, /<NutXuLy v=\{v\} quyen=\{quyen\} nhieuCoSo=/);
  assert.match(ds, /coQuyen\(quyen, x\.lego\)/);
  assert.match(ds, /Nhờ người có quyền thu xử lý/);
  // Cả bảng desktop lẫn thẻ điện thoại đều có.
  assert.equal((ds.match(/<NutXuLy /g) ?? []).length, 2);
  // Màn không tự dựng link theo loại việc (luật nằm ở máy chủ).
  assert.doesNotMatch(ds, /\/thu-ngan\//);
});

test("nút Xử lý nhắc cơ sở của lượt + đường đổi cơ sở do máy chủ dựng (chỉ khi có nhiều cơ sở)", () => {
  const ds = read("../app/(dashboard)/hoa-don/DanhSachHoaDon.tsx");
  assert.match(ds, /nhieuCoSo=\{coSo\.length > 1\}/);
  assert.match(ds, /x\.co_so && x\.doi_co_so_href/);
  assert.match(ds, /href=\{x\.doi_co_so_href\}/);
  assert.doesNotMatch(ds, /chon-co-so/); // đường do máy chủ dựng, màn không tự ghép
});

test("quầy thu không lặng lẽ nhảy sang khách khác khi lượt của liên kết không có trong hàng chờ", () => {
  const quay = read("../app/(dashboard)/thu-ngan/QuayThuNgan.tsx");
  assert.match(quay, /const luotTuUrl = thamSo\?\.get\("luot"\) \?\? null/);
  assert.match(quay, /luotUrlLac/);
  assert.match(quay, /\(luotUrlLac \? null : \(conCho\[0\] \?\? null\)\)/);
  // Một dòng trung tính, không hộp vàng đỏ (Tuyền 14/10): vẫn không tự chọn khách khác.
  assert.match(quay, /Khách này không có trong danh sách chờ thu — chọn khách ở dưới/);
  assert.doesNotMatch(quay, /Máy KHÔNG tự chọn khách khác/);
});

test("Check-out nhận ?luot= (UUID) và tô sáng đúng lượt tồn đọng", () => {
  const page = read("../app/(dashboard)/reception/checkout/page.tsx");
  assert.match(page, /UUID\.test\(sp\.luot\)/);
  assert.match(page, /luotMoSan=\{luot\}/);
  const board = read("../app/(dashboard)/reception/checkout/CheckoutBoard.tsx");
  assert.match(board, /luotNoiBat=\{\s*luotMoSan &&/);
  const ton = read("../app/(dashboard)/reception/checkout/LuotTonDong.tsx");
  assert.match(ton, /luotNoiBat === l\.visit_id/);
  assert.match(ton, /scrollIntoView/);
});

test("lượt cũ từ ?luot= không nằm trong danh sách tồn đọng vẫn hiện (có Đóng lượt) hoặc một dòng trung tính", () => {
  const ton = read("../app/(dashboard)/reception/checkout/LuotTonDong.tsx");
  assert.match(ton, /checkout\?visit_id=\$\{encodeURIComponent\(id\)\}/);
  assert.match(ton, /\[rieng\.luot, \.\.\.ds\]/);
  assert.match(ton, /Lượt này đã đóng\./);
  assert.match(ton, /Không tìm thấy lượt này\./);
  // Lượt đã có trong bảng hôm nay thì bảng lo, không tô thêm.
  const board = read("../app/(dashboard)/reception/checkout/CheckoutBoard.tsx");
  assert.match(board, /!initial\.some\(\(r\) => r\.visit_id === luotMoSan\)/);
});

test("không hộp vàng/đỏ cho việc bình thường: nợ, huỷ, CK đã huỷ, chưa trả lại, cần đối soát", () => {
  const ct = read("../app/(dashboard)/hoa-don/ChiTietHoaDon.tsx");
  assert.doesNotMatch(ct, /bg-warning-bg/);
  assert.doesNotMatch(ct, /chua_tra_lai[^\n]*text-danger/);
  const tt = read("../app/(dashboard)/reports/TomTatCuoiNgay.tsx");
  assert.doesNotMatch(tt, /không khớp công thức/);
  assert.doesNotMatch(tt, /ck_cho_da_huy[\s\S]{0,200}text-warning/);
  const ton = read("../app/(dashboard)/reception/checkout/LuotTonDong.tsx");
  assert.doesNotMatch(ton, /border-warning|bg-warning-bg|tone="warning"/);
});
