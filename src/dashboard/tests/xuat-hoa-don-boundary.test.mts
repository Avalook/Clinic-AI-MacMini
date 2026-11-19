import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");
test("Xuất hoá đơn đứng ngay dưới Danh sách hoá đơn, cửa report.view", () => {
  const nav = read("../app/(dashboard)/nav-items.ts");
  assert.match(nav, /href: "\/hoa-don", label: "Danh sách hoá đơn"[^\n]+\n\s*\{ href: "\/xuat-hoa-don", label: "Xuất hoá đơn"/);
  assert.match(read("../lib/roles.ts"), /"\/xuat-hoa-don": \["report.view"\]/);
  assert.match(read("../app/(dashboard)/xuat-hoa-don/page.tsx"), /requireNavAccess\("\/xuat-hoa-don"\)/);
});
test("màn chỉ chọn phạm vi + tải file; số tiền do máy chủ tính", () => {
  const ui = read("../app/(dashboard)/xuat-hoa-don/XuatHoaDon.tsx");
  assert.match(ui, /\/api\/xuat-hoa-don\?\$\{chuoi\}&xuat=xlsx/);
  assert.match(ui, /AbortController/);
  assert.doesNotMatch(ui, /\.reduce\(/);
  assert.match(read("../app/api/xuat-hoa-don/route.ts"), /\/api\/v1\/hoa-don\/xuat\/xlsx/);
});
test("bảng máy tính có 2 CỘT bác sĩ, mỗi dòng hàng một hàng (Tuyền 19/11)", () => {
  const ui = read("../app/(dashboard)/xuat-hoa-don/XuatHoaDon.tsx");
  // Thứ tự cột: 2 cột bác sĩ đứng SAU "Ghi chú" (Tuyền 19/11).
  const cot = [...ui.matchAll(/^\s*\["([^"]+)", "[^"]*", "[^"]*"\],$/gm)].map(m => m[1]);
  assert.deepEqual(cot, ["STT", "Ngày", "Khách hàng", "Hình thức", "Hàng hoá / dịch vụ",
    "Thành tiền", "Ghi chú", "BS chỉ định", "BS thực hiện"]);
  // Ô bác sĩ là 2 ô CUỐI của hàng (sau ô Ghi chú rowSpan).
  assert.match(ui, /<GhiChu h=\{h\} \/><\/td>[\s\S]*?\{d\.bs_chi_dinh \|\| <span[\s\S]*?\{d\.bs_thuc_hien \|\| <span[\s\S]*?<\/tr>/);
  // Mỗi dòng hàng một <tr>, key duy nhất theo stt + vị trí (trùng key → DOM mồ côi, 16/11).
  assert.match(ui, /key=\{`\$\{h\.stt\}-\$\{i\}`\}/);
  assert.match(ui, /rowSpan=\{n\}/);
  assert.match(ui, /\{d\.bs_chi_dinh \|\| <span/);
  assert.match(ui, /\{d\.bs_thuc_hien \|\| <span/);
  // Thẻ điện thoại vẫn hiện bác sĩ dưới từng dòng.
  assert.match(ui, /BS chỉ định: \{d\.bs_chi_dinh \|\| "—"\} · BS thực hiện: \{d\.bs_thuc_hien \|\| "—"\}/);
});
