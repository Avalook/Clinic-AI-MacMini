import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";

// Theo dõi thuốc (31/10/2026): một tab, mọi lối vào, máy chủ quyết mọi số và chữ.

const doc = (p: string) => readFileSync(new URL(`../${p}`, import.meta.url), "utf8");
const THU_MUC = "app/(dashboard)/pharmacy/inventory";
const kho = doc(`${THU_MUC}/KhoThuoc.tsx`);
const man = doc(`${THU_MUC}/TheoDoiThuoc.tsx`);
const proxy = doc("app/api/pharmacy/[action]/route.ts");

test("tab đổi tên, link cũ the-kho / lich-su vẫn mở đúng tab", () => {
  assert.match(kho, /ma: "theo_doi" as const, nhan: "Theo dõi thuốc"/);
  assert.match(kho, /"the_kho": "theo_doi"/);
  assert.match(kho, /"lich_su": "theo_doi"/);
  assert.equal(existsSync(new URL(`../${THU_MUC}/TheKho.tsx`, import.meta.url)), false);
});

test("ba lối vào từ tên thuốc cùng mở tab Theo dõi thuốc", () => {
  assert.match(kho, /<DanhMucKho[^>]*onXemThe=\{xemThe\}/);
  assert.match(kho, /<XuatNhapTon onXemThe=\{xemThe\}/);
  assert.match(kho, /<InventoryBoard[^>]*onXemThe=\{xemThe\}/);
  assert.match(kho, /setTheoDoi\(\{ id \}\);\s*setTab\("theo_doi"\)/);
});

test("proxy chỉ chuyển tiếp bộ lọc; Excel dùng cùng bộ lọc với màn", () => {
  assert.match(proxy, /"tim-theo-doi":/);
  assert.match(proxy, /"theo-doi-thuoc": \(q\) =>/);
  assert.match(proxy, /theo-doi-thuoc\.xlsx\?\$\{locTheoDoi\(query\)\}/);
  assert.match(man, /theo-doi-thuoc-xlsx\?\$\{thamSo\}/);
});

test("màn chỉ vẽ: không tự đặt tên hành động, không tự tính tồn, không hiện SĐT", () => {
  assert.doesNotMatch(man, /RETURN_RECEIVED|CHUYEN_RA|DISPENSE|txn_type/);
  assert.doesNotMatch(man, /tong\s*-\s*|o_kho\s*\+/);
  assert.doesNotMatch(man, /sdt|phone/i);
  assert.match(man, /t\.tren_ke/);
});

test("khách mở được lượt khám bằng màn Xem lượt có sẵn", () => {
  assert.match(man, /<XemLuot visitId=\{xemLuot\}/);
});
