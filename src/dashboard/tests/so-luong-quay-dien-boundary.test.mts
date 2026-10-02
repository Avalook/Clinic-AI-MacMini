// C14 (01/10/2026) — quầy thu thuốc điền số lượng bác sĩ quên: màn kê đơn đang
// mở chỉ gộp phần quầy điền, KHÔNG đè chữ bác sĩ đang gõ.

import assert from "node:assert/strict";
import test from "node:test";

import { dongTuDon, gopSoLuongQuayDien, type DongDonMayChu } from "../lib/phieu-kham.ts";

const may = (id: string, quantity: string | null, doQuay: boolean): DongDonMayChu => ({
  id,
  drug_catalog_id: null,
  drug_name_raw: "Aspilet",
  quantity,
  dosage_instructions: null,
  caution: null,
  so_luong_do_thu_ngan: doQuay,
});

test("dòng bác sĩ để trống + quầy vừa điền → gộp số, đơn vị và nhãn", () => {
  const hienTai = [dongTuDon(may("a", null, false))];
  const gop = gopSoLuongQuayDien(hienTai, [dongTuDon(may("a", "10 viên", true))]);
  assert.ok(gop);
  assert.equal(gop[0].so_luong, "10");
  assert.equal(gop[0].don_vi, "viên");
  assert.equal(gop[0].so_luong_do_thu_ngan, true);
});

test("bác sĩ đang gõ số khác thì KHÔNG bị đè", () => {
  const hienTai = [dongTuDon(may("a", "3 viên", false))];
  assert.equal(gopSoLuongQuayDien(hienTai, [dongTuDon(may("a", "10 viên", true))]), null);
});

test("quầy sửa lại số mình điền → màn kê đơn theo kịp; không đổi gì thì null", () => {
  const hienTai = [dongTuDon(may("a", "10 viên", true))];
  const sua = gopSoLuongQuayDien(hienTai, [dongTuDon(may("a", "20 viên", true))]);
  assert.equal(sua?.[0].so_luong, "20");
  assert.equal(gopSoLuongQuayDien(hienTai, [dongTuDon(may("a", "10 viên", true))]), null);
});

test("dòng không do quầy điền thì bỏ qua", () => {
  const hienTai = [dongTuDon(may("a", null, false))];
  assert.equal(gopSoLuongQuayDien(hienTai, [dongTuDon(may("a", "10 viên", false))]), null);
});
