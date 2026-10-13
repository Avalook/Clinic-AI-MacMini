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
