// Bản nháp "Lấy thêm thuốc" phải sống qua lần GẮN LẠI khung quầy (16/11/2026).
//
// Prod 16/11: khung `ChinhDonQuay` bị gắn lại sau mỗi lần trang làm mới → thuốc vừa
// chọn + số lượng mất sạch, 13 lượt "Thêm" bị 422 vì số lượng rỗng. "Gắn lại" ở đây
// = một người đọc MỚI (useSyncExternalStore của component mới) đọc lại kho.
import assert from "node:assert/strict";
import test from "node:test";

import type { DongThuoc } from "./phieu-kham.ts";
import { NHAP_RONG, taoKhoNhapLayThem } from "./nhap-lay-them.ts";

const dong = (so_luong: string): DongThuoc => ({
  drug_catalog_id: "11111111-1111-1111-1111-111111111111",
  ten_thuoc: "Thuốc thử",
  duong_dung: "",
  so_luong,
  don_vi: "viên",
  cach_dung: "Ngày 1 viên",
  luu_y: "",
  mau_ma: null,
});

test("gắn lại khung: người đọc mới thấy nguyên nháp (thuốc + số + cách dùng)", () => {
  const kho = taoKhoNhapLayThem();
  const goNghe = kho.nghe(() => {});
  kho.ghi("L1", { dong: [dong("10")] });
  goNghe(); // khung cũ bị gỡ
  const doc = kho.doc("L1"); // khung mới đọc lại
  assert.equal(doc.dong.length, 1);
  assert.equal(doc.dong[0].so_luong, "10");
  assert.equal(doc.dong[0].cach_dung, "Ngày 1 viên");
});

test("422 → nháp còn nguyên, lời từ chối còn sau khi gắn lại", () => {
  const kho = taoKhoNhapLayThem();
  kho.ghi("L1", { dong: [dong("")] });
  kho.ghi("L1", { loi: "“Thuốc thử”: ghi số lượng (vd “10 viên”)." });
  const doc = kho.doc("L1");
  assert.equal(doc.dong.length, 1);
  assert.match(doc.loi ?? "", /ghi số lượng/);
});

test("sửa nháp không xoá lỗi trừ khi nói rõ; gõ lại thì màn tự xoá lỗi", () => {
  const kho = taoKhoNhapLayThem();
  kho.ghi("L1", { dong: [dong("")], loi: "lỗi" });
  kho.ghi("L1", { dong: [dong("5")] });
  assert.equal(kho.doc("L1").loi, "lỗi");
  kho.ghi("L1", { dong: [dong("5")], loi: null });
  assert.equal(kho.doc("L1").loi, null);
  assert.equal(kho.doc("L1").dong[0].so_luong, "5");
});

test("tách theo lượt: nháp lượt này không lọt sang lượt khác", () => {
  const kho = taoKhoNhapLayThem();
  kho.ghi("L1", { dong: [dong("10")] });
  assert.equal(kho.doc("L2"), NHAP_RONG);
});

test("lưu xong thì bỏ nháp; lượt chưa có nháp đọc ra CÙNG một tham chiếu", () => {
  const kho = taoKhoNhapLayThem();
  kho.ghi("L1", { dong: [dong("10")] });
  kho.bo("L1");
  assert.equal(kho.doc("L1"), NHAP_RONG);
  // useSyncExternalStore đòi ảnh chụp ổn định — đọc hai lần phải là một tham chiếu.
  assert.equal(kho.doc("L9"), kho.doc("L9"));
  kho.ghi("L1", { dong: [dong("10")] });
  assert.equal(kho.doc("L1"), kho.doc("L1"));
});

test("nháp rỗng và không lỗi thì không giữ chỗ trong kho", () => {
  const kho = taoKhoNhapLayThem();
  kho.ghi("L1", { dong: [dong("10")] });
  kho.ghi("L1", { dong: [] });
  assert.equal(kho.doc("L1"), NHAP_RONG);
});

test("hai khung cùng một lượt cùng được báo khi nháp đổi", () => {
  const kho = taoKhoNhapLayThem();
  let a = 0;
  let b = 0;
  const goA = kho.nghe(() => a++);
  kho.nghe(() => b++);
  kho.ghi("L1", { dong: [dong("1")] });
  goA();
  kho.ghi("L1", { dong: [dong("2")] });
  assert.equal(a, 1);
  assert.equal(b, 2);
});
