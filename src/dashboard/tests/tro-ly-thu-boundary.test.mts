// Màn thử trợ lý AI (30/10/2026): cửa quyền, đường gọi, và "màn chỉ vẽ".
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path: string): string =>
  readFileSync(new URL(path, import.meta.url), "utf8");

const page = read("../app/(dashboard)/tro-ly-thu/page.tsx");
const man = read("../app/(dashboard)/tro-ly-thu/TroLyThu.tsx");
const proxy = read("../app/api/tro-ly/route.ts");
const roles = read("../lib/roles.ts");

test("màn gác bằng quyền ops.view và không bị công tắc mở tạm chạm vào", () => {
  assert.match(page, /requireNavAccess\("\/tro-ly-thu"\)/);
  assert.match(roles, /"\/tro-ly-thu": \["ops\.view"\]/);
  const khongMo = roles.slice(roles.indexOf("const KHONG_MO_THEO_CONG_TAC"));
  assert.match(khongMo.slice(0, khongMo.indexOf("];")), /"\/tro-ly-thu"/);
});

test("màn chỉ gọi proxy /api/tro-ly; proxy chỉ chuyển tiếp danh sách trắng", () => {
  assert.doesNotMatch(man, /\/api\/v1\//);
  assert.match(man, /"\/api\/tro-ly/);
  // Mã trên URL được kiểm hình trước khi ghép vào đường backend.
  assert.match(proxy, /UUID_RE\.test\(b\.id\)/);
  assert.match(proxy, /UUID_RE\.test\(b\.tin_id\)/);
  assert.doesNotMatch(proxy, /\[\.\.\./);
});

test("luật chặn và công cụ không nằm trong TSX", () => {
  assert.doesNotMatch(man, /ra mau|kiem_tra|bo_dau|khan_cap"\s*\?/);
});
