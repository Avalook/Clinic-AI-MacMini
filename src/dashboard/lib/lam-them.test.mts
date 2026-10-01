import assert from "node:assert/strict";
import test from "node:test";

import { chiaLoLamThem } from "./lam-them.ts";

test("chia lượt thành nhiều gói để không mất dòng sau mốc 300", () => {
  const ids = Array.from({ length: 501 }, (_, i) => `luot-${i}`);
  const lo = chiaLoLamThem(ids);
  assert.deepEqual(lo.map((x) => x.length), [250, 250, 1]);
  assert.deepEqual(lo.flat(), ids);
});

test("bỏ mã rỗng và mã trùng nhưng giữ thứ tự", () => {
  assert.deepEqual(chiaLoLamThem(["a", "", "b", "a"], 2), [["a", "b"]]);
});
