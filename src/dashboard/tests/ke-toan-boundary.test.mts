import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");

test("lego Kế toán: cửa theo QUYỀN accounting.finance.full, không theo vai", () => {
  const roles = read("../lib/roles.ts");
  assert.match(roles, /"\/ke-toan": \["accounting\.finance\.full"\]/);
  // Không có dòng vai cho màn này: vai `ACCOUNTANT` (16/10) chỉ là nhãn, không mở
  // /ke-toan; còn mã gói mẫu KE_TOAN thì không bao giờ là vai (Tuyền 27/09: chỉ lego).
  assert.doesNotMatch(roles, /KE_TOAN/);
  assert.doesNotMatch(roles, /"\/ke-toan": \[[^\]]*"ACCOUNTANT"/);
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
