import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// EXCEL ĐỊA CHỈ KHÁCH (chị Hoài, 11/11/2026). Xuất hàng loạt SĐT + địa chỉ: chỉ
// Kế toán / Quản lý. Máy chủ gác (test DB `test_xuat_dia_chi_khach_db.py`); bài này
// canh phía màn: nút chỉ hiện cho đúng quyền máy chủ hỏi, tải ĐÚNG bộ lọc đang xem,
// proxy không chép thêm tham số nào.

const doc = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");
const trang = doc("../app/(dashboard)/patient-list/page.tsx");
const view = doc("../app/(dashboard)/patient-list/PatientListView.tsx");
const route = doc("../app/api/patients/dia-chi-xlsx/route.ts");
const svc = doc("../../clinicai/services/xuat_dia_chi_khach.py");
const router = doc("../../clinicai/api/v1/patients.py");

test("màn hỏi đúng chuỗi quyền máy chủ gác", () => {
  const m = /^QUYEN_XUAT = "([a-z_.]+)"/m.exec(svc);
  assert.ok(m, "không đọc được QUYEN_XUAT");
  assert.match(trang, new RegExp(`xuatDiaChi = theoQuyen\\(\\["${m[1].replace(/\./g, "\\.")}"\\], false\\)`));
  assert.match(router, /cua_quyen\(QUYEN_XUAT_DIA_CHI\)/);
});

test("nút chỉ hiện khi có cờ, tải theo ô tìm đã gửi + tab đang chọn", () => {
  const i = view.indexOf("{xuatDiaChi ? (");
  assert.ok(i > 0, "nút phải nằm trong nhánh xuatDiaChi");
  const nut = view.slice(i, view.indexOf(") : null}", i));
  assert.match(nut, /href=\{`\/api\/patients\/dia-chi-xlsx\?/);
  assert.match(nut, /q: qUrl/);
  assert.match(nut, /loc: filter/);
  assert.match(nut, /Tải Excel địa chỉ khách/);
  assert.equal([...view.matchAll(/dia-chi-xlsx/g)].length, 1, "chỉ một lối tải");
});

test("proxy chỉ chép q + loc và gọi đúng đường máy chủ", () => {
  assert.match(route, /\[\["q", 200\], \["loc", 40\]\]/);
  assert.match(route, /\/api\/v1\/patients\/danh-sach-xlsx\?/);
  assert.match(router, /@router\.get\("\/patients\/danh-sach-xlsx"\)/);
  assert.doesNotMatch(route, /input\.forEach|for \(const \[k, v\] of input/);
});
