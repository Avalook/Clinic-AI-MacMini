import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");

// "Xuất hoá đơn về công ty" ở quầy thu (Tuyền 16/10/2026): tick THEO LƯỢT thu, danh
// sách công ty do máy chủ báo, màn chỉ vẽ + gửi cong_ty_id.

test("quầy một hoá đơn, khối dịch vụ và khối thuốc đều có ô tick công ty theo lượt", () => {
  const mot = read("../app/(dashboard)/thu-ngan/HoaDonMot.tsx");
  assert.match(mot, /<CongTyKhiThu congTy=\{congTy\} onDoi=\{setCongTyId\} \/>/);
  assert.match(mot, /congTyId: congTyId \?\? undefined/);
  // Khoá gửi lại phải chứa công ty — bấm lại sau khi đổi tick không dùng nhầm khoá cũ.
  assert.match(mot, /congTyId \?\? "",\n\s*\]\.join\("\|"\)/);
  const quay = read("../app/(dashboard)/thu-ngan/QuayThuNgan.tsx");
  assert.match(quay, /<CongTyKhiThu congTy=\{congTy\} onDoi=\{setCongTyId\} \/>/);
  assert.equal((quay.match(/congTy=\{l\.cong_ty\}/g) ?? []).length, 3);
  assert.match(quay, /congTyId \?\? "",\n\s*\),/);
  assert.match(quay, /\.\.\.\(p\.congTyId \? \{ congTyId: p\.congTyId \} : \{\}\)/);
  assert.match(quay, /\.\.\.\(congTyId \? \{ congTyId \} : \{\}\)/);
});

test("tiền đã ghi mà công ty chưa gắn → báo rõ, không giả làm thất bại", () => {
  const quay = read("../app/(dashboard)/thu-ngan/QuayThuNgan.tsx");
  assert.match(quay, /d\?\.cong_ty_loi\) loiThu = `Đã ghi lần thu, nhưng chưa gắn công ty/);
});

test("ô tick chỉ CHỌN công ty có sẵn trong hồ sơ: không ô nhập, không luật nghiệp vụ", () => {
  const ui = read("../app/(dashboard)/thu-ngan/CongTyKhiThu.tsx");
  assert.match(ui, /Xuất hoá đơn về công ty/);
  assert.doesNotMatch(ui, /<input[^>]*type="text"/);
  assert.doesNotMatch(ui, /fetch\(/);
  assert.match(ui, /disabled=\{ds\.length === 0\}/);
});

test("route chuyển cong_ty_id nguyên văn sang máy chủ", () => {
  const route = read("../app/api/payment/route.ts");
  assert.match(route, /cong_ty_id: p\.congTyId \?\? null/);
});

test("ô 'Người mua' của công ty không còn ô nhập — file luôn ghi khách thật", () => {
  const form = read("../app/(dashboard)/hoa-don/FormCongTy.tsx");
  assert.doesNotMatch(form, /ten: "Người mua/);
});
