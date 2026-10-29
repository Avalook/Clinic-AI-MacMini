import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";
import ts from "typescript";
// CI chạy test:boundary: kéo cả kiểm thử hành vi nền vào cùng cổng kiểm.
import "../lib/sdt.test.mts";
import "./ten-khach.test.mts";

// Đếm JSX con, không đếm props truyền cho TenKhach, chuỗi hay comment.
// `ten` được đếm rộng (cả vài tên dịch vụ) để không bỏ sót các alias khách.
function demTenNguon(source: string): number {
  const file = ts.createSourceFile("screen.tsx", source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  let count = 0;
  function visit(node: ts.Node) {
    if (ts.isJsxExpression(node) && node.expression && !ts.isJsxAttribute(node.parent)) {
      let found = false;
      function field(n: ts.Node) {
        if (ts.isJsxElement(n) || ts.isJsxSelfClosingElement(n) || ts.isJsxFragment(n)) return;
        if (ts.isPropertyAccessExpression(n) && /^(full_name|ten|ten_khach|patient_name|patientName|ten_benh_nhan)$/.test(n.name.text)) found = true;
        ts.forEachChild(n, field);
      }
      field(node.expression);
      if (found) count += 1;
    }
    ts.forEachChild(node, visit);
  }
  visit(file);
  return count;
}

function files(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    return entry.isDirectory() ? files(path) : path.endsWith(".tsx") ? [path] : [];
  });
}

test("bộ đếm nhận tên trực tiếp và không đếm props, chuỗi/comment", () => {
  assert.equal(demTenNguon('<><b>{x.full_name}</b><p>{d.ten || "—"}</p><i>{l.ten_khach}</i></>'), 3);
  assert.equal(demTenNguon('<TenKhach ten={x.full_name} sdt={x.phone} />'), 0);
  assert.equal(demTenNguon('<>{/* {x.full_name} */}<b>{"x.full_name"}</b></>'), 0);
});

test("số chỗ vẽ tên trực tiếp chỉ được giảm khi chuyển sang TenKhach", () => {
  const root = new URL("../app/(dashboard)/", import.meta.url).pathname;
  const count = files(root).reduce((sum, path) => sum + demTenNguon(readFileSync(path, "utf8")), 0);
  const TRAN = 272; // Ghim đúng số đo H0; hạ trần khi chuyển màn ở H1 trở đi.
  assert.equal(count, TRAN, `Hiện ${count} chỗ; không thêm tên trực tiếp. Nếu giảm, hạ TRAN.`);
});
