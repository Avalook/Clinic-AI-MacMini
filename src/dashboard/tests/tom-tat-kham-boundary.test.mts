import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// In "Tóm tắt bệnh án — 3 lần khám gần nhất" (Tuyền duyệt demo 30/10/2026).
// Trang chỉ VẼ: chọn lượt, ngưỡng bất thường, xu hướng đều ở máy chủ
// (`services/tom_tat_kham.py`). Lối vào: nút "Lịch sử khám" dùng chung + /customers.
const doc = (f: string) => readFileSync(new URL(f, import.meta.url), "utf8");
const TRANG = doc("../app/print/tom-tat-kham/[patientId]/page.tsx");
const IN = doc("../app/print/tom-tat-kham/[patientId]/InTomTatKham.tsx");
const LS = doc("../app/(dashboard)/_lam-viec/LichSuKham.tsx");
const KH = doc("../app/(dashboard)/customers/ThanhLuotKham.tsx");
const PROXY = doc("../app/api/ho-so-kham/route.ts");

test("cùng cửa quyền + khổ A4 + đầu phiếu như các phiếu in khác", () => {
  assert.match(TRANG, /await requireInPhieu\(\)/);
  assert.match(IN, /<KieuInA4 \/>/);
  assert.match(IN, /<DauTrangIn/);
  assert.match(IN, /<KhoiBenhNhanIn/);
});

test("đọc một nguồn máy chủ, chỉ chuyển tiếp", () => {
  assert.match(IN, /xem: "tom-tat-kham"/);
  assert.match(PROXY, /\/api\/v1\/ho-so-kham\/tom-tat-kham\?/);
});

test("không luật nghiệp vụ trong TSX: ô đỏ theo `bat_thuong`, xu hướng theo `xu_huong`", () => {
  assert.match(IN, /bat_thuong\.includes\("systolic"\)/);
  assert.match(IN, /l\.xu_huong\.huyet_ap/);
  assert.match(IN, /l\.xu_huong\.can_nang/);
  // Không tự so ngưỡng huyết áp / mạch / nhiệt trong màn.
  assert.doesNotMatch(IN, /(>=|>|<=|<)\s*(140|90|38|50|120|94)\b/);
  assert.doesNotMatch(IN, /\.sort\(|\.reverse\(/, "thứ tự cũ → mới do máy chủ xếp");
});

test("chữ ký bác sĩ lượt mới nhất ở CUỐI phiếu, sau bảng", () => {
  const bang = IN.indexOf("<table");
  const ky = IN.indexOf("goi.bac_si_ky");
  assert.ok(bang > 0 && ky > bang);
  assert.ok(IN.lastIndexOf("</footer>") > IN.lastIndexOf("</table>"));
});

test("chọn số lần, bỏ chọn lượt, ẩn/hiện sản khoa (tự ẩn khi không có thai)", () => {
  assert.match(IN, /so_lan: String\(soLan\)/);
  assert.match(IN, /q\.set\("bo", bo\.join\(","\)\)/);
  assert.match(IN, /goi\.co_thai \? \(/);
  assert.match(IN, /const hienThai = goi\.co_thai && !anThai/);
});

test("lối vào: nút Lịch sử khám dùng chung + In PDF trả khách ở /customers", () => {
  assert.match(LS, /\/print\/tom-tat-kham\/\$\{clinicPatientId\}/);
  assert.match(LS, /In tóm tắt 3 lần khám/);
  assert.match(KH, /duongTomTat\(clinicPatientId\)/);
});
