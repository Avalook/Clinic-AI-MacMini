import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import { runInNewContext } from "node:vm";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

// Khách không mua cả đơn + mở lại (16/11/2026). Nút nào hiện là do máy chủ quyết
// (`khong_lay_ca_don`, `mo_lai_ca_don`, `thao_tac.mo_lai`) — màn không tự suy.

const doc = (p: string) => readFileSync(new URL(`../${p}`, import.meta.url), "utf8");
const khoi = doc("app/(dashboard)/pharmacy/KhachKhongLayCaDon.tsx");
const dong = doc("app/(dashboard)/pharmacy/DongThuoc.tsx");
const board = doc("app/(dashboard)/pharmacy/PharmacyBoard.tsx");
const proxy = doc("app/api/pharmacy/[action]/route.ts");

function nap(): React.ComponentType<Record<string, unknown>> {
  const exports: { default?: React.ComponentType<Record<string, unknown>> } = {};
  const require = createRequire(import.meta.url);
  const code = ts.transpileModule(khoi, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
  }).outputText;
  runInNewContext(code, { exports, require: (path: string) => {
    if (path === "next/navigation") return { useRouter: () => ({ refresh() {} }) };
    if (path === "../form-ui") return { INPUT: "" };
    if (path === "../customers/khoa-mot-lan") return { dinhDanhThaoTac: String, khoaThaoTac: String, xongThaoTac() {} };
    if (path === "./DongThuoc") return { CHAM: "" };
    if (path === "@/components/ui/Button") {
      return function MockButton(p: { children: React.ReactNode }) {
        return React.createElement("button", { type: "button" }, p.children);
      };
    }
    return require(path);
  } });
  assert.ok(exports.default);
  return exports.default;
}

const luot = (co: Record<string, boolean>) => ({ visit_id: "v1", dong: [], ...co });

test("nút cả đơn hiện đúng theo cờ máy chủ", () => {
  const K = nap();
  const chiDong = renderToStaticMarkup(React.createElement(K, { luot: luot({ khong_lay_ca_don: true }) }));
  assert.match(chiDong, />Khách không mua đơn này<\/button>/);
  assert.doesNotMatch(chiDong, /Mở lại cả đơn/);
  const chiMo = renderToStaticMarkup(React.createElement(K, { luot: luot({ mo_lai_ca_don: true }) }));
  assert.match(chiMo, />Mở lại cả đơn<\/button>/);
  assert.doesNotMatch(chiMo, /Khách không mua đơn này/);
  assert.equal(renderToStaticMarkup(React.createElement(K, { luot: luot({}) })), "");
});

test("gọi đúng thao tác qua proxy danh sách trắng, không tự suy luật", () => {
  for (const a of ["khong-lay-ca-don", "mo-lai-dong", "mo-lai-ca-don"]) {
    assert.match(proxy, new RegExp(`"${a}": "/api/v1/pharmacy/${a}"`));
  }
  assert.match(khoi, /goi\(\s*"khong-lay-ca-don"/);
  assert.match(khoi, /goi\(\s*"mo-lai-ca-don"/);
  assert.match(dong, /tt\.mo_lai \?/);
  assert.match(dong, /goi\("mo-lai-dong", \{ prescription_id: dong\.id \}\)/);
  // Key vẫn theo lượt, nhưng có tiền tố riêng: `key={luot.visit_id}` trần trùng key
  // anh em `BanLeThu` → khung bán lẻ gắn lại + DOM mồ côi (16/11/2026,
  // tests/nha-thuoc-key-anh-em-boundary).
  assert.match(board, /<KhachKhongLayCaDon key=\{`khong-lay:\$\{luot\.visit_id\}`\} luot=\{luot\} \/>/);
  assert.doesNotMatch(khoi, /window\.confirm|giai_doan|lan_thu|refusal_reason/);
});
