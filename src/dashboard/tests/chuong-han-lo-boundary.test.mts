import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import ts from "typescript";

const require = createRequire(import.meta.url);
const code = ts.transpileModule(
  readFileSync(new URL("../lib/chi-tiet-thong-bao.ts", import.meta.url), "utf8"),
  { compilerOptions: { module: ts.ModuleKind.CommonJS } },
).outputText;
const m = { exports: {} as { chiTietThongBao: (t: Record<string, unknown>) => string } };
new Function("module", "exports", "require", code)(m, m.exports, require);

test("chuông hệ thống không cần người gọi, nguồn hiện đúng", () => {
  assert.equal(m.exports.chiTietThongBao({ nguoi_goi: null, nhan_nguon: "Hệ thống — hạn lô", noi_dung: "2 lô" }), "Hệ thống — hạn lô · 2 lô");
});
test("chuông cũ và chỉ định bị bỏ giữ chữ cũ, null không lỗi", () => {
  assert.equal(m.exports.chiTietThongBao({ nguoi_goi: "Hà", noi_dung: "x" }), "Hà gọi · x");
  assert.equal(m.exports.chiTietThongBao({ nguoi_goi: "Hà", chi_hoan_tac: true, noi_dung: "x" }), "x");
  assert.equal(m.exports.chiTietThongBao({ nguoi_goi: null, noi_dung: "x" }), "x");
});
