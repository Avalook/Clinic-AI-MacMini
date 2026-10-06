import assert from "node:assert/strict";
import test from "node:test";

import { cacSoTrang, khoangDong, type MucSoTrang } from "./so-trang.ts";

const chu = (ds: MucSoTrang[]) => ds.map((m) => (m.loai === "so" ? String(m.so) : "…")).join(" ");
const hep = (ds: MucSoTrang[]) =>
  ds.filter((m) => m.hep).map((m) => (m.loai === "so" ? m.so : 0));

test("ít trang: in đủ, không có dấu …", () => {
  assert.equal(chu(cacSoTrang(1, 1)), "1");
  assert.equal(chu(cacSoTrang(2, 3)), "1 2 3");
  assert.equal(chu(cacSoTrang(1, 5)), "1 2 3 4 5");
});

test("nhiều trang: đầu + cuối + 2 trang mỗi bên, hở một trang thì in số", () => {
  assert.equal(chu(cacSoTrang(1, 175)), "1 2 3 … 175");
  assert.equal(chu(cacSoTrang(6, 175)), "1 … 4 5 6 7 8 … 175");
  assert.equal(chu(cacSoTrang(4, 175)), "1 2 3 4 5 6 … 175"); // không "1 … 2"
  assert.equal(chu(cacSoTrang(175, 175)), "1 … 173 174 175");
  assert.equal(chu(cacSoTrang(6, 175, 1)), "1 … 5 6 7 … 175");
});

test("màn hẹp chỉ giữ trang đang xem ± 1", () => {
  assert.deepEqual(hep(cacSoTrang(6, 175)), [5, 6, 7]);
  assert.deepEqual(hep(cacSoTrang(1, 175)), [1, 2]);
  assert.deepEqual(hep(cacSoTrang(175, 175)), [174, 175]);
});

test("đầu vào rác → 1 trang / trang 1, không ném; trang vượt → trang cuối", () => {
  for (const rac of [Number.NaN, -1, 0, 2.5, "3", null, undefined, Infinity]) {
    assert.equal(chu(cacSoTrang(rac, 3)), "1 2 3");
    assert.equal(chu(cacSoTrang(1, rac)), "1");
  }
  assert.deepEqual(hep(cacSoTrang(99, 3)), [2, 3]);
});

test("khoảng dòng 'Hiển thị x–y'", () => {
  assert.deepEqual(khoangDong(1, 50, 50), { tu: 1, den: 50 });
  assert.deepEqual(khoangDong(3, 50, 7), { tu: 101, den: 107 });
  assert.deepEqual(khoangDong(1, 50, 0), { tu: 0, den: 0 });
});
