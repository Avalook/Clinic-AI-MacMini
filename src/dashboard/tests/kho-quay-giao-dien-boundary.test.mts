import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import { runInNewContext } from "node:vm";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

// Giao diện tách KHO / QUẦY (G7-2, 14/10/2026): màn chỉ vẽ + gửi lệnh, luật ở máy chủ.

const doc = (p: string) => readFileSync(new URL(`../${p}`, import.meta.url), "utf8");
const proxy = doc("app/api/pharmacy/[action]/route.ts");
const guiKhoSrc = doc("app/(dashboard)/pharmacy/inventory/gui-kho.ts");
const dongThuoc = doc("app/(dashboard)/pharmacy/DongThuoc.tsx");
const khoThuoc = doc("app/(dashboard)/pharmacy/inventory/KhoThuoc.tsx");

type Comp = React.ComponentType<Record<string, unknown>>;

/** Dịch một component TSX ra CommonJS rồi nạp với các import mock (như test G3a-B). */
function nap(duongDan: string, mock: Record<string, unknown>): Comp {
  const exports: { default?: Comp } = {};
  const require = createRequire(import.meta.url);
  const code = ts.transpileModule(doc(duongDan), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
  }).outputText;
  runInNewContext(code, {
    exports,
    crypto: { randomUUID: () => "00000000-0000-4000-8000-000000000000" },
    fetch: () => new Promise(() => {}),
    require: (p: string) => (p in mock ? mock[p] : require(p)),
  });
  assert.ok(exports.default, `không nạp được ${duongDan}`);
  return exports.default;
}

const Nut = (p: { children?: React.ReactNode }) => React.createElement("button", { type: "button" }, p.children);
const Chip = (p: { children?: React.ReactNode }) => React.createElement("span", {}, p.children);
const MOCK = {
  "next/navigation": { useRouter: () => ({ refresh() {} }) },
  "@/components/ui/Button": Nut,
  "@/components/ui/Chip": Chip,
  "../../form-ui": { INPUT: "i", TBL_DIV: "d", TBL_HEAD: "h", TBL_WRAP: "w" },
  "./gui-kho": { guiKho: async () => ({ ok: true, data: null }), soKho: (n: unknown) => String(n), tienVnd: String },
  "./NhapLo": () => null,
};

const lo = (id: string, noi: "KHO" | "QUAY", ton: number) => ({
  id,
  drug_catalog_id: "thuoc-1",
  batch_code: `L-${id}`,
  expiry_date: "2027-01-01",
  quantity_on_hand: ton,
  unit: "viên",
  cost_price: null,
  received_at: null,
  trang_thai_han: "con_han",
  canh_bao_han: false,
  huy_lo_txn_id: null,
  noi_chua: noi,
  drug: { name_base: "Paracetamol", name_raw: "Paracetamol", variant: null },
});

test("proxy cho đi ba đường G7 và gui-kho khai đủ", () => {
  for (const a of ["chuyen-kho", "hoan-tac-chuyen-kho", "tach-kho-quay"]) {
    assert.match(proxy, new RegExp(`"${a}": "/api/v1/pharmacy/${a}"`));
    assert.match(guiKhoSrc, new RegExp(`"${a}"`));
  }
});

test("tab Chuyển kho có trong Kho thuốc; chip KHO/QUẦY chỉ hiện khi bật tách", () => {
  assert.match(khoThuoc, /ma: "chuyen_kho", nhan: "Chuyển kho"/);
  assert.match(khoThuoc, /tachKhoQuay=\{tachKhoQuay\}/);
  const Board = nap("app/(dashboard)/pharmacy/inventory/InventoryBoard.tsx", MOCK);
  const batches = [lo("a", "KHO", 10), lo("b", "QUAY", 5)];
  const tat = renderToStaticMarkup(React.createElement(Board, { batches, thuoc: [], tachKhoQuay: false }));
  assert.doesNotMatch(tat, /Nơi chứa/);
  const bat = renderToStaticMarkup(React.createElement(Board, { batches, thuoc: [], tachKhoQuay: true }));
  assert.match(bat, /Nơi chứa/);
  assert.match(bat, /<span>KHO<\/span>/);
  assert.match(bat, /<span>QUẦY<\/span>/);
});

test("ChuyenKho: tắt = nút Bật (chỉ người sửa được), bật = form chỉ liệt kê lô ở nơi nguồn", () => {
  const Chuyen = nap("app/(dashboard)/pharmacy/inventory/ChuyenKho.tsx", MOCK);
  const batches = [lo("kho1", "KHO", 10), lo("quay1", "QUAY", 5), lo("kho0", "KHO", 0)];
  const tat = renderToStaticMarkup(
    React.createElement(Chuyen, { batches, tachKhoQuay: false, suaTachDuoc: true, ghiDuoc: true }),
  );
  assert.match(tat, /Bật tách kho \/ quầy/);
  assert.doesNotMatch(tat, /Tạo phiếu chuyển/);
  const khongQuyen = renderToStaticMarkup(
    React.createElement(Chuyen, { batches, tachKhoQuay: false, suaTachDuoc: false, ghiDuoc: true }),
  );
  assert.doesNotMatch(khongQuyen, /Bật tách kho/);
  const bat = renderToStaticMarkup(
    React.createElement(Chuyen, { batches, tachKhoQuay: true, suaTachDuoc: true, ghiDuoc: true }),
  );
  assert.match(bat, /Tắt tách kho \/ quầy/);
  assert.match(bat, /L-kho1/);
  assert.doesNotMatch(bat, /L-quay1/); // chiều mặc định Kho → Quầy: chỉ lô ở kho
  assert.doesNotMatch(bat, /L-kho0/); // lô hết tồn không chuyển được
  const chiXem = renderToStaticMarkup(
    React.createElement(Chuyen, { batches, tachKhoQuay: true, suaTachDuoc: false, ghiDuoc: false }),
  );
  assert.doesNotMatch(chiXem, /Tạo phiếu chuyển/);
});

test("quầy hết lô mà kho còn → nút chuyển ngay ở dòng đơn, không thêm window.confirm", () => {
  assert.match(dongThuoc, /<KhoConChuyenQuay/);
  assert.match(dongThuoc, /dong\.lo_goi_y\.length === 0/);
  const KhoCon = nap("app/(dashboard)/pharmacy/KhoConChuyenQuay.tsx", {
    ...MOCK,
    "../form-ui": { INPUT: "i" },
    "./ban-thuoc": { fmtNgay: (s: string) => s, fmtSo: (n: unknown) => String(n) },
    "./inventory/gui-kho": MOCK["./gui-kho"],
  });
  const khoCon = [{ drug_batch_id: "k1", batch_code: "LK1", expiry_date: "2027-01-01", unit: "viên", ton: 7 }];
  const html = renderToStaticMarkup(React.createElement(KhoCon, { khoCon, can: 3, tenThuoc: "Para" }));
  assert.match(html, /kho còn 7 viên/);
  assert.match(html, /Chuyển sang quầy/);
  const xem = renderToStaticMarkup(React.createElement(KhoCon, { khoCon, can: 3, tenThuoc: "Para", chiXem: true }));
  assert.doesNotMatch(xem, /<button/);
  for (const f of [
    "app/(dashboard)/pharmacy/KhoConChuyenQuay.tsx",
    "app/(dashboard)/pharmacy/inventory/ChuyenKho.tsx",
  ]) {
    assert.doesNotMatch(doc(f), /window\.confirm/);
  }
});
