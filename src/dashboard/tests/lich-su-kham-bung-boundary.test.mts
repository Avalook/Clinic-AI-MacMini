// [Lịch sử khám] bấm là bung danh sách lượt cũ ngay dưới nút, rê chuột hiện
// tóm tắt, cuối có "Tìm theo ngày · xem mọi lượt" mở hộp lớn — thay dòng chip
// "Lượt khám trước" riêng ở Bàn khám (Tuyền 29/10/2026).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const doc = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");
const LS = doc("../app/(dashboard)/_lam-viec/LichSuKham.tsx");
const LT = doc("../app/(dashboard)/doctor/board/LuotKhamTruoc.tsx");
const HT = doc("../app/(dashboard)/_lam-viec/HanhTrinhKhach.tsx");

test("nút Lịch sử khám bung danh sách, rê chuột có tóm tắt, có lối sang hộp lớn", () => {
  assert.match(LS, /aria-expanded=\{menu\} onClick=\{\(\) => setMenu\(\(x\) => !x\)\}/);
  assert.match(LS, /onMouseEnter=\{\(\) => setHien\(l\.visit_id\)\}/);
  assert.match(LS, /\/api\/clinical-forms\/history\?clinic_patient_id=/);
  assert.match(LS, /Tìm theo ngày · xem mọi lượt/);
});

test("Bàn khám không còn dòng chip 'Lượt khám trước' riêng", () => {
  assert.doesNotMatch(LT.replace(/^\s*\/\/.*$/gm, ""), /Lượt khám trước:/);
});

test("hộp hành trình: tiêu đề chỉ là tên khách", () => {
  assert.match(HT, /\{ten \|\| "Hành trình khách"\}/);
  assert.doesNotMatch(HT, /Hành trình khách\{ten \?/);
});
