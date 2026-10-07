import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// Khối 4 "Điều trị" của hồ sơ khám (Tuyền chốt 07/10/2026, T6): hai ô chữ của
// LƯỢT, bảng riêng — KHÔNG nhét vào 7 mẫu phiếu JSON; tự lưu; in kèm khi có chữ.
const doc = (f: string) => readFileSync(new URL(f, import.meta.url), "utf8");
const LIB = doc("../lib/phieu-kham.ts");
const PHIEU = doc("../app/(dashboard)/_lam-viec/phieu-kham/PhieuKham.tsx");
const LUOT = doc("../app/(dashboard)/_lam-viec/phieu-kham/PhieuKhamLuot.tsx");
const KHOI = doc("../app/(dashboard)/_lam-viec/phieu-kham/KhoiDieuTri.tsx");
const IN = doc("../app/print/phieu-kham/[visitId]/InPhieuKham.tsx");

test("bốn khối, khối 4 không có mục của mẫu phiếu", () => {
  assert.match(LIB, /\{ so: 4, ten: "Điều trị", muc: \[\] \}/);
  // Ba khối cũ giữ nguyên mục (phiếu đã lưu vẫn đọc đúng).
  assert.match(LIB, /\{ so: 1, ten: "Thông tin cơ bản", muc: \["A", "B"\] \}/);
  assert.match(LIB, /\{ so: 3, ten: "Chỉ định điều trị", muc: \["D", "E", "F", "G"\] \}/);
});

test("phiếu vẽ khối 4 qua shell; không có shell thì vẫn ba khối như cũ", () => {
  assert.match(PHIEU, /\{khoi === 4 \? oDieuTri : null\}/);
  assert.match(PHIEU, /oDieuTri \? KHOI : KHOI\.filter\(\(k\) => k\.so !== 4\)/);
  assert.match(LUOT, /oDieuTri=\{chiMuc \? undefined : <KhoiDieuTri/);
  // Hồ sơ tối giản (lượt không phiếu) cũng có khối.
  assert.match(LUOT.slice(LUOT.indexOf("if (chonDuoc) {")), /<KhoiDieuTri/);
});

test("khối tự lưu qua hàng đợi chung, gửi bản đang nhìn để chống đè", () => {
  assert.match(KHOI, /useTuLuu\(/);
  assert.match(KHOI, /phien_ban: daLuu\.current\.ban/);
  assert.match(KHOI, /r\.status === 409/);
  assert.match(KHOI, /Cảm nhận/);
  assert.match(KHOI, /Vấn đề sau điều trị/);
});

test("bản in kèm khối Điều trị khi có nội dung", () => {
  assert.match(IN, /xem=dieu-tri/);
  assert.match(IN, /dt\.cam_nhan\.trim\(\) \|\| dt\.van_de_sau\.trim\(\)/);
});
