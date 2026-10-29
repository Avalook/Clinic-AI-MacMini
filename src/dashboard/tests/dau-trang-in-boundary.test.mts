// Đầu phiếu in (phiếu khám, phiếu kết quả): phòng khám + tên phiếu căn giữa,
// địa chỉ in nghiêng có nhãn, mã / booking / ngày bên trái (Tuyền 29/10/2026).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const doc = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");

test("đầu phiếu in căn giữa, địa chỉ nghiêng có nhãn", () => {
  const k = doc("../app/print/KhoiIn.tsx");
  assert.match(k, /<div className="text-center">/);
  assert.match(k, /italic text-ink-muted">Địa chỉ: \{diaChi\}/);
  assert.doesNotMatch(k, /text-right/);
  for (const p of ["../app/print/phieu-kham/[visitId]/InPhieuKham.tsx", "../app/print/ket-qua/[orderId]/InKetQua.tsx"]) {
    assert.match(doc(p), /coSo=\{[^}]+\}\s*diaChi=\{[^}]+\}/);
  }
});
