// S0-2 (18/09/2026). Phiếu Phụ khoa từng ĐẢO nhãn: "Khám trong" chứa môi lớn/
// môi bé/âm hộ… còn "Khám ngoài" chứa âm đạo/CTC/tử cung. Tuyền chốt sửa theo
// lâm sàng (khớp phiếu HMVS vốn đúng). KEY Ô GIỮ NGUYÊN để dữ liệu cũ khớp ô.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");

const NGOAI = ["moi_lon", "moi_be", "am_vat", "am_ho", "mang_trinh", "tang_sinh_mon"];
const TRONG = ["am_dao", "co_tu_cung", "than_tu_cung", "phan_phu", "tui_cung"];

function nhom(src: string, tieuDe: RegExp): string {
  const i = src.search(tieuDe);
  assert.ok(i >= 0, `không thấy nhóm ${tieuDe}`);
  const het = src.indexOf("],", i);
  return src.slice(i, het);
}

test("Phụ khoa: Khám ngoài = cơ quan sinh dục ngoài, Khám trong = âm đạo/CTC/tử cung/phần phụ", () => {
  const pk = read("../lib/form-schemas/pk.ts");
  const ngoai = nhom(pk, /title: "Khám chuyên khoa — Khám ngoài/);
  const trong = nhom(pk, /title: "Khám chuyên khoa — Khám trong/);
  for (const k of NGOAI) assert.ok(ngoai.includes(`key: "${k}"`), `${k} phải ở Khám ngoài`);
  for (const k of TRONG) assert.ok(trong.includes(`key: "${k}"`), `${k} phải ở Khám trong`);
  // Ngoài trước, trong sau — cùng thứ tự với phiếu HMVS.
  assert.ok(pk.indexOf("Khám chuyên khoa — Khám ngoài") < pk.indexOf("Khám chuyên khoa — Khám trong"));
  assert.doesNotMatch(pk, /HOÁN ĐỔI/);
});
