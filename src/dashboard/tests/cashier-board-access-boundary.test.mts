import assert from "node:assert/strict";
import test from "node:test";

import { canSeeNav } from "../lib/roles.ts";

test("reception is not offered the reconciliation board it cannot safely read", () => {
  assert.equal(canSeeNav("RECEPTION", "/cashier/board"), false);
  assert.equal(canSeeNav("CASHIER", "/cashier/board"), true);
  // TRƯỞNG CA KHÔNG CÒN THẤY MỤC NÀY — quyết định của Quang (04/08/2026), khi
  // cắt sidebar Trưởng ca từ 28 mục xuống 8: *"chỉ giữ lại cái gì cần theo bản
  // trước đó antigravity làm thôi, những cái khác quản lý hệ thống làm là được"*.
  //
  // Điều bài kiểm này thật sự canh vẫn nguyên: bảng đối soát chỉ mở cho người
  // có trách nhiệm thu tiền. Danh sách ai được thấy là quyết định vận hành, và
  // nó vừa đổi.
  assert.equal(canSeeNav("TRUONG_CA", "/cashier/board"), false);
  assert.equal(canSeeNav("MANAGEMENT", "/cashier/board"), true);
});
