import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// SINH HIỆU CHỈ ĐO Ở MỘT CHỖ (Tuyền chốt 17/09/2026: "cái nào cũ thì bỏ").
// Biểu mẫu đón-khám cũ lưu sinh hiệu mà không báo "đã đo" cho luồng khám, nên
// khách kẹt ngoài hàng chờ bác sĩ. Nó chỉ còn xem + nút dẫn sang màn đo.
const form = readFileSync(
  new URL("../app/(dashboard)/tasks/ClinicalRecordForm.tsx", import.meta.url),
  "utf8",
);

test("biểu mẫu bệnh án không còn nút 'Lưu sinh hiệu' của đường đón-khám cũ", () => {
  assert.doesNotMatch(form, /Lưu sinh hiệu/);
  assert.doesNotMatch(form, /saveVitals/);
});

test("đường đón-khám cũ dẫn sang màn Đo sinh hiệu", () => {
  assert.match(form, /href="\/do-sinh-hieu"/);
});
