import assert from "node:assert/strict";
import test from "node:test";

import { khopTimKhach, type KhachTim } from "./tim-khach-phong.ts";

const mai: KhachTim = { ten: "Bùi Thị Ngọc Mai", ma: "BN-2026-332789", so: [10, 7, null] };
const k0141: KhachTim = { ten: "Khách 0141", ma: "BN-2026-749811", so: [11] };

test("ô rỗng khớp hết", () => {
  assert.equal(khopTimKhach("", mai), true);
  assert.equal(khopTimKhach("   ", mai), true);
});

test("tên bỏ dấu, không phân biệt hoa thường, đủ mọi từ", () => {
  assert.equal(khopTimKhach("ngoc mai", mai), true);
  assert.equal(khopTimKhach("NGỌC", mai), true);
  assert.equal(khopTimKhach("mai bui", mai), true);
  assert.equal(khopTimKhach("ngoc lan", mai), false);
});

test("mã khách", () => {
  assert.equal(khopTimKhach("332789", mai), true);
  assert.equal(khopTimKhach("bn-2026-3327", mai), true);
  assert.equal(khopTimKhach("749811", mai), false);
});

test("số ngắn khớp ĐÚNG số tiếp đón / booking, không kéo theo số dài hơn", () => {
  assert.equal(khopTimKhach("10", mai), true);
  assert.equal(khopTimKhach("#10", mai), true);
  assert.equal(khopTimKhach("1", mai), false);
  assert.equal(khopTimKhach("7", mai), true);
});

test("số trong tên khách (bỏ số 0 đầu)", () => {
  assert.equal(khopTimKhach("141", k0141), true);
  assert.equal(khopTimKhach("0141", k0141), true);
  assert.equal(khopTimKhach("11", k0141), true);
  assert.equal(khopTimKhach("14", k0141), false);
});

test("thiếu tên / mã không làm vỡ", () => {
  assert.equal(khopTimKhach("abc", { ten: null, ma: undefined, so: [] }), false);
  assert.equal(khopTimKhach("5", { ten: null, ma: null, so: [5] }), true);
});
