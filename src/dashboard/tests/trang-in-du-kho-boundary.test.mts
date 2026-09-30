// TRANG IN PHẢI ĐỦ KHỔ GIẤY (30/09/2026). Thân trang là flex cột; <main mx-auto>
// không `w-full` thì CO THEO NỘI DUNG — phiếu khám ít chữ in ra chỉ bằng nửa tờ
// A4 (đo bằng Chrome in PDF: 370px trong khổ ~700px).
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

function tsx(dir: string): string[] {
  return readdirSync(dir).flatMap((t) => {
    const p = join(dir, t);
    return statSync(p).isDirectory() ? tsx(p) : p.endsWith(".tsx") ? [p] : [];
  });
}

test("mọi <main mx-auto> của trang in có w-full", () => {
  const goc = new URL("../app/print/", import.meta.url).pathname;
  const thieu: string[] = [];
  for (const f of tsx(goc)) {
    for (const m of readFileSync(f, "utf8").matchAll(/<main className="([^"]*)"/g)) {
      const lop = m[1].split(/\s+/);
      if (lop.includes("mx-auto") && !lop.includes("w-full")) thieu.push(f.slice(goc.length));
    }
  }
  assert.deepEqual(thieu, []);
});
