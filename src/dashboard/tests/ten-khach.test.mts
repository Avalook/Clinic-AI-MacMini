import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import * as sdt from "../lib/sdt.ts";

const require = createRequire(import.meta.url);
function loadTsx(path: string, dependencies: Record<string, unknown> = {}) {
  const source = readFileSync(new URL(path, import.meta.url), "utf8");
  const compiled = ts.transpileModule(source, {
    compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS },
  }).outputText;
  const exports: Record<string, React.ComponentType<Record<string, unknown>>> = {};
  new Function("require", "exports", compiled)((name: string) => dependencies[name] ?? require(name), exports);
  return exports;
}
const soLuot = loadTsx("../components/ui/SoLuot.tsx");
const { default: TenKhach } = loadTsx("../components/ui/TenKhach.tsx", {
  "./SoLuot": soLuot,
  "../../lib/sdt": sdt,
});

test("ba chế độ × hai bố cục giữ tên/mã, chỉ hiện số được yêu cầu", () => {
  for (const bo of ["ngang", "doc"]) {
    for (const che of ["day_du", "che", "an"]) {
      const html = renderToStaticMarkup(React.createElement(TenKhach, {
        ten: "Nguyễn Thị Mẫu", ma: "DEMO-001", sdt: "0912345678", bo, che,
      }));
      assert.match(html, /Nguyễn Thị Mẫu/);
      assert.match(html, /DEMO-001/);
      assert.equal(html.includes("0912 345 678"), che === "day_du");
      assert.equal(html.includes("0912 ••• 678"), che === "che");
      assert.match(html, /truncate/);
      assert.equal(html.includes("md:flex-row"), bo === "ngang");
    }
  }
});

test("trống thì bỏ dòng số, số quốc tế/rác giữ đúng cách đọc", () => {
  for (const [raw, expected] of [[null, ""], ["", ""], ["0912", "0912"], ["+14155552671", "+1 415 555 2671"]]) {
    const html = renderToStaticMarkup(React.createElement(TenKhach, { ten: "Mẫu", sdt: raw }));
    assert.doesNotMatch(html, /Chưa có SĐT/);
    if (expected) assert.ok(html.includes(expected));
    else assert.doesNotMatch(html, /tabular-nums/);
  }
  const html = renderToStaticMarkup(React.createElement(TenKhach, {
    ten: "Mẫu", soLuot: { booking: 12, checkin: 5 },
  }));
  assert.match(html, /Booking #12/);
  assert.match(html, /Check-in 5/);
});
