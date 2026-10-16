import assert from "node:assert/strict";
import test from "node:test";

import { bsTen } from "./doctor-name.ts";

test("bsTen: tên trần thì thêm BS", () => {
  assert.equal(bsTen("Phan Chí Thành"), "BS Phan Chí Thành");
});

test("bsTen: đã là 'Bác sĩ …' (kiểu tên duy nhất trên prod) thì không lặp", () => {
  assert.equal(bsTen("Bác sĩ Phan Chí Thành"), "Bác sĩ Phan Chí Thành");
  assert.equal(bsTen("bác sĩ Thành"), "bác sĩ Thành");
});

test("bsTen: đã có 'BS …' thì không lặp", () => {
  assert.equal(bsTen("BS Thành"), "Bác sĩ Thành");
  assert.equal(bsTen("BS. Nguyễn Thành Đạt"), "Bác sĩ Nguyễn Thành Đạt");
});

test("bsTen: chuỗi ghép cũ 'Bác sĩ · TS.BS. X' chỉ ra một chức danh", () => {
  assert.equal(bsTen("Bác sĩ · TS.BS. Phan Chí Thành"), "Bác sĩ Phan Chí Thành");
});

test("bsTen: chức danh khác bác sĩ không bị gắn BS", () => {
  assert.equal(bsTen("Điều dưỡng Thuý"), "Điều dưỡng Thuý");
});

test("bsTen: rác / rỗng → chuỗi rỗng", () => {
  assert.equal(bsTen(null), "");
  assert.equal(bsTen(undefined), "");
  assert.equal(bsTen("   "), "");
});
