import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// Quy đổi hộp ↔ viên lúc nhập (17/10/2026). Luật nằm ở máy chủ
// (test_quy_doi_don_vi_db.py); ở đây chỉ canh các lối nhập gửi đúng ô hệ số và
// proxy cho phép đúng đường xem trước.

const doc = (p: string) => readFileSync(new URL(`../${p}`, import.meta.url), "utf8");
const kho = "app/(dashboard)/pharmacy/inventory";

test("Nhập lô và Phiếu nhập đều gắn ô quy đổi và gửi hệ số + xác nhận", () => {
  for (const f of ["NhapLo", "PhieuNhap"]) {
    const s = doc(`${kho}/${f}.tsx`);
    assert.ok(s.includes('import QuyDoiNhap from "./QuyDoiNhap"'), `${f} thiếu QuyDoiNhap`);
    assert.ok(s.includes("<QuyDoiNhap"), `${f} chưa vẽ ô quy đổi`);
    assert.match(s, /he_so: [^,\n]*\.trim\(\) \|\| null/, `${f} không gửi he_so`);
    assert.ok(s.includes("xac_nhan_he_so"), `${f} không gửi xac_nhan_he_so`);
  }
});

test("ô quy đổi chỉ hỏi máy chủ và vẽ lại câu trả lời, không tự tính hệ số", () => {
  const s = doc(`${kho}/QuyDoiNhap.tsx`);
  assert.ok(s.includes('docKho<XemQuyDoi>("quy-doi"'));
  assert.ok(s.includes("so_luong_quy_doi"), "số '= N' do máy chủ trả");
  assert.ok(s.includes("can_xac_nhan"), "hệ số lạ do máy chủ quyết");
  assert.ok(!/\*\s*Number\(/.test(s), "không nhân số lượng × hệ số ở TSX");
  // Đổi thuốc/đơn vị thì hệ số gõ dở bị bỏ (thuộc về đơn vị cũ).
  assert.match(s, /onHeSo\(""\);\s*onXacNhan\(false\);/);
});

test("proxy cho đọc quy-doi và chặn id thuốc không phải uuid", () => {
  const r = doc("app/api/pharmacy/[action]/route.ts");
  assert.ok(r.includes('"quy-doi": (q) =>'));
  assert.ok(r.includes("/api/v1/pharmacy/quy-doi?"));
  assert.match(r, /"quy-doi": \(q\) => \{\s*const id = q\.get\("drug_catalog_id"\)[\s\S]*UUID_RE\.test\(id\)/);
  assert.ok(doc(`${kho}/gui-kho.ts`).includes('"tra-ma" | "tem-lo" | "quy-doi"'));
});

test("phiếu nhập: thuốc đã có đơn vị bán thì khỏi cảnh báo 'tồn riêng'", () => {
  const s = doc(`${kho}/PhieuNhap.tsx`);
  assert.ok(s.includes("if (t?.don_vi_ban) return null;"));
});
