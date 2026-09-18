// Batch pilot 18/09/2026 — MHT ở phiếu Nội tiết tách ba loại thông tin.
// Bản cũ gộp "chỉ định / chống chỉ định / cân nhắc" vào MỘT radio loại trừ
// nhau: ghi được yếu tố chống chỉ định thì mất yếu tố chỉ định, và "quyết định
// của bác sĩ" lẫn vào cùng ô ấy.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const nt = readFileSync(new URL("../lib/form-schemas/nt.ts", import.meta.url), "utf8");

function nhom(tieuDe: string): string {
  const i = nt.indexOf(`title: "${tieuDe}`);
  assert.ok(i >= 0, `không thấy nhóm ${tieuDe}`);
  return nt.slice(i, nt.indexOf("\n    },", i));
}

test("yếu tố chỉ định / chống chỉ định / thận trọng là ô độc lập, không radio", () => {
  const g = nhom("MHT — Yếu tố ghi nhận");
  for (const k of ["mht_yeu_to_chi_dinh", "mht_yeu_to_chong_chi_dinh", "mht_yeu_to_than_trong"]) {
    assert.ok(g.includes(`key: "${k}"`), `thiếu ${k}`);
  }
  assert.doesNotMatch(g, /type: "radio"/);
});

test("quyết định bác sĩ là trường riêng, giữ key và giá trị cũ", () => {
  const g = nhom("MHT — Quyết định của bác sĩ");
  assert.ok(g.includes('key: "mht_quyet_dinh"'));
  for (const v of ["chi_dinh", "chong_chi_dinh", "can_nhac"]) {
    assert.ok(g.includes(`value: "${v}"`), `mất giá trị cũ ${v}`);
  }
  assert.doesNotMatch(g, /mht_yeu_to_|mht_lieu|mht_ten_thuoc/);
});

test("kế hoạch dùng thuốc tách phác đồ / tên thuốc / đường dùng / liều", () => {
  const g = nhom("MHT — Kế hoạch dùng thuốc");
  for (const k of ["mht_phac_do", "mht_ten_thuoc", "mht_duong_dung", "mht_lieu"]) {
    assert.ok(g.includes(`key: "${k}"`), `thiếu ${k}`);
  }
});
