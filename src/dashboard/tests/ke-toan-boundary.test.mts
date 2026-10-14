import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");

test("lego Kế toán: cửa theo QUYỀN accounting.finance.full, không theo vai", () => {
  const roles = read("../lib/roles.ts");
  assert.match(roles, /"\/ke-toan": \["accounting\.finance\.full"\]/);
  // Không có dòng vai cho màn này: vai KE_TOAN không tồn tại (Tuyền 27/09: chỉ lego).
  assert.doesNotMatch(roles, /KE_TOAN/);
  assert.match(read("../app/(dashboard)/nav-items.ts"), /href: "\/ke-toan", label: "Kế toán"/);
  assert.match(read("../app/(dashboard)/ke-toan/page.tsx"), /requireNavAccess\("\/ke-toan"\)/);
});

test("Theo hàng hoá: màn chỉ chọn phạm vi + tải file; số do máy chủ tính", () => {
  const ui = read("../app/(dashboard)/ke-toan/KeToan.tsx");
  assert.match(ui, /\/api\/theo-hang-hoa\?\$\{chuoi\}&xuat=xlsx/);
  assert.match(ui, /AbortController/);
  assert.doesNotMatch(ui, /\.reduce\(/);
  const route = read("../app/api/theo-hang-hoa/route.ts");
  assert.match(route, /\/api\/v1\/hoa-don\/theo-hang-hoa\/xlsx/);
  assert.match(route, /\/api\/v1\/hoa-don\/theo-hang-hoa\?/);
});
