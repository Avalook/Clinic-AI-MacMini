import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// Phòng dịch vụ (15/10/2026): dòng "blocked" (khách đang ở bước/phòng khác) vẫn có nút
// [Bắt đầu] (nhận chéo, hệ thống ghi dấu vết) — câu trên dòng KHÔNG được nói "chưa làm
// bước này được" (mâu thuẫn với nút bấm được).
const src = readFileSync(
  new URL("../app/(dashboard)/phong/[ma]/PhongDichVu.tsx", import.meta.url),
  "utf8",
);

test("câu 'khách ở bước khác' không còn nói chưa làm được", () => {
  assert.ok(!src.includes("chưa làm bước này được"), "câu cũ mâu thuẫn với nút Bắt đầu");
  assert.ok(src.includes("vẫn bấm Bắt đầu được"), "phải nói rõ vẫn bắt đầu được và có ghi dấu vết");
});

test("nút Bắt đầu vẫn hiện cho dòng chưa làm (chuaLam) dù khách ở bước khác", () => {
  assert.ok(/chuaLam\s*&&\s*th\s*\?/.test(src), "điều kiện hiện nút Bắt đầu không được thêm cổng blocked");
});
