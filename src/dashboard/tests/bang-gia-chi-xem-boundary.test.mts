import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { quyenMoDuocMan, vaoDuocMan } from "../lib/roles.ts";

// XEM BẢNG GIÁ (11/11/2026): kế toán mở được `/cashier/dich-vu` bằng quyền CHỈ XEM
// (`price.service.view`), màn vẽ chữ thay ô sửa theo cờ máy chủ `sua_gia_duoc`.
// Lệnh ghi vẫn bị router chặn (test DB `test_quyen_xem_bang_gia_db.py`) — bài này
// canh phía màn: không để lộ ô sửa cho người chỉ xem.

const doc = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");
const bang = doc("../app/(dashboard)/cashier/DanhMucDichVuPhong.tsx");
const vatTu = doc("../app/(dashboard)/cashier/VatTuBangGia.tsx");

test("quyền chỉ xem mở được màn Bảng giá, không mở màn khác", () => {
  const xem = ["price.service.view"];
  assert.equal(quyenMoDuocMan(xem, "/cashier/dich-vu"), true);
  assert.equal(vaoDuocMan("/cashier/dich-vu", [], xem), true);
  for (const khac of ["/ke-toan", "/settings", "/pharmacy/inventory", "/kho-vat-tu"]) {
    assert.equal(vaoDuocMan(khac, [], xem), false, khac);
  }
});

test("thiếu cờ máy chủ thì coi là chỉ xem (đóng mặc định)", () => {
  assert.match(bang, /const chiXem = goi\.sua_gia_duoc !== true;/);
  // Màn không tự suy quyền theo vai.
  assert.doesNotMatch(bang, /ACCOUNTANT|MANAGEMENT|ClinicRole|getVai|\bvai\b/);
});

test("chỉ xem: không có khối Thêm dịch vụ, dòng dịch vụ và vật tư nhận cờ", () => {
  const them = bang.indexOf("<ThemDichVu");
  const cong = bang.lastIndexOf("{chiXem ? null : (", them);
  assert.ok(cong > 0 && them - cong < 400, "ThemDichVu phải nằm trong nhánh không chỉ xem");
  assert.match(bang, /chiXem=\{chiXem\}\s+nhapGia=/);
  assert.match(bang, /<VatTuBangGia[\s\S]{0,120}chiXem=\{chiXem\}/);
});

test("vật tư chỉ xem: ô giá và panel sửa thuộc tính chỉ ở nhánh sửa", () => {
  const nhanh = vatTu.indexOf("{chiXem ? (");
  assert.ok(nhanh > 0);
  for (const o of ["aria-label={`Đơn giá", "<VatTuThuocTinh", 'type="checkbox"']) {
    assert.ok(vatTu.indexOf(o) > nhanh, `${o} phải nằm sau nhánh chỉ xem`);
  }
});
