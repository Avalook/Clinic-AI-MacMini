import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");
const vatTuQuay = read("../app/(dashboard)/thu-ngan/VatTuQuay.tsx");
const bangGia = read("../app/(dashboard)/cashier/VatTuBangGia.tsx");
const kieu = read("../lib/vat-tu.ts");
const service = read("../../clinicai/services/vat_tu_service.py");
const danhMucService = read("../../clinicai/services/danh_muc_dich_vu_service.py");
const migration = read("../../../supabase/migrations/20261019160000_vat_tu_duyet_chi_quan_ly.sql");
const khoPage = read("../app/(dashboard)/kho-vat-tu/page.tsx");
const bangGiaPage = read("../app/(dashboard)/cashier/dich-vu/page.tsx");

test("quầy: ô nguyên nhân bán thêm gửi kèm mỗi lần thêm, dây BẬT thì khoá nút thêm tới khi đủ chữ", () => {
  assert.match(vatTuQuay, /ly_do_ban: lyDoBan\.trim\(\)/);
  assert.match(vatTuQuay, /goi\.bat_ly_do_ban \? " \(bắt buộc, 5–500 ký tự\)"/);
  // Khoá chỉ là gợi ý cho người bấm — máy chủ vẫn ép (không luật nghiệp vụ trong TSX).
  assert.match(vatTuQuay, /thieuLyDo && !daCoDong\(m\.id\)/);
  assert.match(vatTuQuay, /Nguyên nhân: \{d\.ly_do_ban\}/);
  assert.match(kieu, /bat_ly_do_ban: boolean/);
  assert.match(kieu, /ly_do_ban: string \| null/);
});

test("quầy: hàng cần duyệt chỉ được Quản lý duyệt", () => {
  assert.match(vatTuQuay, /Chỉ Quản lý có quyền mới bán được/);
  assert.match(vatTuQuay, /Quản lý đang đăng nhập xác nhận giao dịch này/);
  assert.doesNotMatch(vatTuQuay, /Bạn là quản lý/);
  assert.doesNotMatch(vatTuQuay, /Trưởng ca/);
  // Việc bình thường (cần duyệt) dùng màu trung tính — không vàng/đỏ (Tuyền 14/10).
  assert.doesNotMatch(vatTuQuay, /bg-warning-bg|text-warning/);
  assert.doesNotMatch(bangGia, /tone="warning">Cần/);
});

test("nhân viên không thể ghi tên Quản lý thay cho người duyệt thật", () => {
  assert.match(vatTuQuay, /m\.chon_nhanh && \(!m\.can_ql_duyet \|\| goi\.la_quan_ly\)/);
  assert.match(vatTuQuay, /timVatTu\(goi\.danh_muc, tim\)\.filter\([\s\S]*!m\.can_ql_duyet \|\| goi\.la_quan_ly/);
  assert.doesNotMatch(vatTuQuay, /Người đã duyệt|goi\.quan_ly\.map/);
  assert.match(service, /if not await _duoc_duyet\(conn, identity\):/);
  assert.match(service, /if r\["can_ql_duyet"\] and not cho_hien_hang_can_duyet:/);
  assert.match(danhMucService, /identity\.vai_goc\.value == "MANAGEMENT"/);
  assert.match(danhMucService, /await can\(conn, identity, "vat_tu\.approve"\)/);
  assert.match(danhMucService, /not m\["can_ql_duyet"\] and not m\["can_duyet_nhap"\]/);
  assert.match(service, /duyet_boi[\s\S]*identity\.staff_id/);
  assert.match(service, /set_config\('app\.staff_id', \$1, true\)/);
  assert.match(migration, /current_setting\('app\.staff_id', true\)/);
  assert.match(migration, /IF actor IS NOT NULL AND actor IS DISTINCT FROM NEW\.chon_boi THEN/);
  assert.doesNotMatch(migration, /IF actor IS NULL THEN[\s\S]{0,120}thiếu người thao tác đã xác thực/);
  assert.match(migration, /NEW\.duyet_ly_do IS DISTINCT FROM OLD\.duyet_ly_do/);
  assert.match(migration, /IF sp\.can_ql_duyet OR EXISTS \([\s\S]*NEW\.service_price_id[\s\S]*chỉ Quản lý có quyền mới sửa hoặc bỏ mặt hàng cần duyệt/);
  assert.doesNotMatch(service, /kq\["quan_ly"\]/);
});

test("mặt hàng cần duyệt chỉ Quản lý được chỉnh số lượng hoặc bỏ", () => {
  assert.match(vatTuQuay, /const khoaTheoQuanLy = d\.can_ql_duyet && !goi\.la_quan_ly/);
  assert.match(vatTuQuay, /chỉ Quản lý được sửa/);
  assert.match(vatTuQuay, /\) : khoaTheoQuanLy \? \(/);
});

test("các cờ phân quyền vật tư chỉ hiện trong giao diện membership Quản lý", () => {
  for (const page of [khoPage, bangGiaPage]) {
    assert.match(page, /laQuanLyDuyetVatTu/);
    assert.doesNotMatch(page, /laQuanLy=\{quyen\.has\("vat_tu\.approve"\)\}/);
  }
  const clinicSession = read("../lib/clinic-session.ts");
  assert.match(clinicSession, /laQuanLy && quyen\.has\("vat_tu\.approve"\)/);
  assert.match(bangGia, /ds\.filter\(\(d\) => !d\.can_ql_duyet && !d\.can_duyet_nhap\)/);
});
