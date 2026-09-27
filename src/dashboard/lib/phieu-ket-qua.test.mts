import assert from "node:assert/strict";
import test from "node:test";

import { ghepConTrong, gopGiaTri, tachGiaTri } from "./phieu-ket-qua.ts";

const khung = [
  { block: [{ ma: "a", ten: "Tử cung" }, { ma: "b", ten: "Buồng trứng" }] },
  { block: [{ ma: "c", ten: "Kết luận" }, { ma: "d", ten: "Kết luận" }, { ma: "e" }] },
];

test("ghepConTrong: gắn mã theo thứ tự khung, kể cả hai ô trùng tên", () => {
  assert.deepEqual(ghepConTrong(khung, ["Buồng trứng", "Kết luận"]), [
    { ma: "b", ten: "Buồng trứng" },
    { ma: "c", ten: "Kết luận" },
  ]);
  assert.deepEqual(ghepConTrong(khung, ["Kết luận", "Kết luận", "e"]), [
    { ma: "c", ten: "Kết luận" },
    { ma: "d", ten: "Kết luận" },
    { ma: "e", ten: "e" },
  ]);
  assert.deepEqual(ghepConTrong(khung, []), []);
});

test("ghepConTrong: rác không ném", () => {
  assert.deepEqual(ghepConTrong(khung, null), []);
  assert.deepEqual(ghepConTrong(khung, "Tử cung"), []);
  assert.deepEqual(ghepConTrong(khung, [1, null, "Tử cung"]), [{ ma: "a", ten: "Tử cung" }]);
  assert.deepEqual(ghepConTrong(khung, ["không có"]), []);
  assert.deepEqual(ghepConTrong([{ block: null }, {} as never], ["x"]), []);
});

test("gopGiaTri: ô bảng `ma::cột` gộp về một ô, bỏ ô rỗng", () => {
  assert.deepEqual(gopGiaTri({ a: "12", "t::A": "5", "t::B": "", "t::C": "7", b: "" }), {
    a: { gia_tri: "12", nguon: "USER" },
    t: { gia_tri: { A: "5", C: "7" }, nguon: "USER" },
  });
});

test("tachGiaTri ↔ gopGiaTri đi vòng không đổi", () => {
  const may = {
    a: { gia_tri: "12", nguon: "USER" },
    t: { gia_tri: { A: "5", C: "7" }, nguon: "USER" },
  };
  assert.deepEqual(tachGiaTri(may), { a: "12", "t::A": "5", "t::C": "7" });
  assert.deepEqual(gopGiaTri(tachGiaTri(may)), may);
  assert.deepEqual(tachGiaTri({ n: { gia_tri: null, nguon: "USER" } }), { n: "" });
});
