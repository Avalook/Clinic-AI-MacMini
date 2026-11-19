// Anh em cùng thẻ chi tiết lượt ở Nhà thuốc KHÔNG được trùng key (16/11/2026).
//
// `BanLeThu` và `KhachKhongLayCaDon` cùng nằm trong một thẻ, từng cùng mang
// `key={luot.visit_id}`. React so con theo key thì lạc một fiber — không dùng lại,
// không xoá: khung bán lẻ bị gắn lại sau mỗi lần trang làm mới và bản cũ nằm lại
// thành DOM mồ côi (prod 16/11: khung hiện 2–3 lần; gõ Số lượng vào bản chết không
// ăn, 13 lượt "Thêm" bị 422). Bản build prod không cảnh báo trùng key — máy này giữ.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const bang = readFileSync(
  new URL("../app/(dashboard)/pharmacy/PharmacyBoard.tsx", import.meta.url),
  "utf8",
);

const keyCua = (comp: string): string => {
  // key là template literal (`ban-le:${…}`) hoặc biểu thức trần không có `}`.
  const m = bang.match(new RegExp(`<${comp}\\s+key=\\{(\`[^\`]*\`|[^}]*)\\}`));
  assert.ok(m, `không thấy <${comp} key=…>`);
  return m[1];
};

test("BanLeThu và KhachKhongLayCaDon mang key khác nhau", () => {
  assert.notEqual(keyCua("BanLeThu"), keyCua("KhachKhongLayCaDon"));
});

test("không còn key trần `luot.visit_id` cho con của thẻ chi tiết", () => {
  assert.doesNotMatch(bang, /key=\{luot\.visit_id\}/);
});
