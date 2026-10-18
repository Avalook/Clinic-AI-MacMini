import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = (path: string) =>
  readFileSync(new URL(path, import.meta.url), "utf8");

test("xóa thông báo ẩn riêng trên máy chủ và đồng bộ badge dùng chung", () => {
  const context = source("../app/(dashboard)/NotificationContext.tsx");
  const header = source("../app/(dashboard)/GlobalHeader.tsx");
  const nav = source("../app/(dashboard)/Nav.tsx");
  const homeBell = source("../app/(dashboard)/RosterBell.tsx");
  const proxy = source("../app/api/thong-bao/route.ts");

  assert.match(context, /anTatCaThongBao/);
  assert.match(context, /method:\s*"DELETE"/);
  assert.match(context, /setNotifs\(\[\]\)/);
  assert.match(context, /setThongBao\(\[\]\)/);
  assert.match(context, /setUnread\(0\)/);
  assert.match(header, /Xóa tất cả/);
  assert.match(nav, /unread\s*>\s*0/);
  assert.match(homeBell, /unread\s*>\s*0/);
  assert.match(proxy, /export async function DELETE/);
});
