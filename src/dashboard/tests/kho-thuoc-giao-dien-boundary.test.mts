import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const doc = (duongDan: string) => readFileSync(new URL(duongDan, import.meta.url), "utf8");
const kho = doc("../app/(dashboard)/pharmacy/inventory/KhoThuoc.tsx");
const ton = doc("../app/(dashboard)/pharmacy/inventory/InventoryBoard.tsx");
const kiem = doc("../app/(dashboard)/pharmacy/inventory/KiemKeCa.tsx");
const xuat = doc("../components/ui/XuatBangTrongVung.tsx");
const nhap = doc("../app/(dashboard)/pharmacy/inventory/PhieuNhap.tsx");
const danhMuc = doc("../app/(dashboard)/pharmacy/inventory/DanhMucKho.tsx");
const baoCaoKho = doc("../app/(dashboard)/pharmacy/inventory/XuatNhapTon.tsx");
const trangKho = doc("../app/(dashboard)/pharmacy/inventory/page.tsx");

test("báo cáo kho chỉ nằm ở khu KHO; tab báo cáo cũ vẫn mở đúng tab mới", () => {
  assert.match(kho, /const TAB_KHO[^\n]*"bao_cao_kho"/);
  assert.doesNotMatch(kho, /const TAB_QUAY[^\n]*"bao_cao/);
  assert.match(kho, /"bao_cao": "bao_cao_kho"/);
});

test("trạng thái hạn thay cảnh báo kho và cho biết số lô theo từng trạng thái", () => {
  assert.match(ton, /const statusCounts = useMemo/);
  assert.match(ton, /STATE_LABEL\[f\]/);
  assert.match(ton, /statusCounts\[f\]/);
  assert.match(ton, /chua_co_han: "Chưa điền hạn"/);
  assert.match(ton, /aria-label="Lọc lô theo tình trạng hạn dùng"/);
  assert.doesNotMatch(ton, /bấm để lọc|bấm để xem|Cảnh báo kho thuốc/);
  assert.doesNotMatch(ton, /Tổng tồn \(theo từng đơn vị\)/);
});

test("phiếu kiểm đầu ca và cuối ca không lẫn; phiếu đột xuất có nhóm riêng", () => {
  assert.match(kiem, /p\.loai === loaiCoDinh/);
  assert.match(kiem, /Phiếu kiểm đột xuất trong ngày/);
  assert.doesNotMatch(kiem, /Phiếu đầu ca trong ngày|Phiếu cuối ca trong ngày/);
  assert.doesNotMatch(kiem, /Bắt đầu kiểm kê/);
  assert.match(kiem, /aria-label="Phiếu kiểm trong ca này"/);
  assert.match(kiem, /await goi<Phieu>\("POST", URL_GOC, \{ ngay, ca, loai: loaiDangKiem \}\)/);
});

test("nút xuất Excel lấy dữ liệu bảng/list đang hiển thị", () => {
  assert.match(kho, /<XuatBangTrongVung/);
  assert.match(xuat, /xuatBangDangXem/);
  assert.match(xuat, /ul\.rounded-card, ul\.space-y-3/);
  assert.match(xuat, /Xuất Excel/);
});

test("nút Xuất Excel nằm cùng hàng với tab con của kho/quầy", () => {
  assert.match(kho, /<XuatBangTrongVung[\s\S]*?thanhCongCu=\{/);
  assert.match(xuat, /thanhCongCu\?: ReactNode/);
  assert.match(xuat, /justify-between/);
});

test("dòng nhập thuốc gọn, nhãn ngắn và các ô có bề ngang theo mục đích", () => {
  assert.match(nhap, /lg:grid-cols-\[minmax\(0,1\.6fr\)_minmax\(0,\.8fr\)_minmax\(0,1fr\)_minmax\(0,\.7fr\)_minmax\(0,\.7fr\)_minmax\(0,1fr\)\]/);
  assert.match(nhap, /<span className=\{LABEL\}>Hạn dùng<\/span>/);
  assert.doesNotMatch(nhap, /Hạn dùng \(có thể nhập sau\)/);
});

test("danh mục gọi rõ cột tồn là số lượng trong kho", () => {
  assert.match(danhMuc, /Số lượng trong kho/);
  assert.doesNotMatch(danhMuc, /<th className="px-3 py-2 text-right">Tồn<\/th>/);
});

test("báo cáo kho dùng bộ chọn lịch khoảng ngày gọn, bỏ phần mô tả và thanh ngày cũ", () => {
  assert.doesNotMatch(kho, /Số thuốc vào – ra – còn theo khoảng ngày/);
  assert.doesNotMatch(baoCaoKho, /Báo cáo kho theo thời gian|Chọn khoảng ngày để xem tồn đầu/);
  assert.doesNotMatch(baoCaoKho, /ThanhNgay|Hôm nay|Tất cả|Tùy chọn|Tuỳ chọn/);
  assert.match(baoCaoKho, /aria-label="Từ ngày"/);
  assert.match(baoCaoKho, /aria-label="Đến ngày"/);
  assert.match(baoCaoKho, /type="date"/);
  assert.match(baoCaoKho, /congNgay\(homNay, -365\)/);
  assert.match(baoCaoKho, /xuat-nhap-ton-xlsx\?tu=\$\{kq\.tu\}&den=\$\{kq\.den\}/);
});

test("form nhập lô tự đóng khi bấm thao tác khác trong danh sách kho", () => {
  assert.match(ton, /onClickCapture=\{/);
  assert.match(ton, /closest\("\[data-nhap-lo-form\], \[data-mo-nhap-lo\]"\)/);
  assert.match(ton, /closest\("button, a, \[role=tab\]"\)/);
  assert.match(ton, /data-nhap-lo-form/);
  assert.match(ton, /onClick=\{\(\) => setMoNhap\(\(mo\) => !mo\)\}/);
});

test("trang Kho thuốc không lặp nút mở khách mua thuốc", () => {
  assert.doesNotMatch(kho, /KhachMuaThuoc|moBanLe/);
  assert.doesNotMatch(trangKho, /moBanLe|QUYEN_BAN_LE/);
});
