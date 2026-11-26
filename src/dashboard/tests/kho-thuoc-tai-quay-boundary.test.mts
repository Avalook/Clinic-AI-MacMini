import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import { runInNewContext } from "node:vm";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

// Tab "Thuốc tại quầy" (Tuyền 16/11): cơ sở tách kho / quầy thì tab kho chỉ vẽ lô KHO,
// lô QUẦY nằm ở nút đầu hàng bên QUẦY — trước đây tab kho vẽ cả hai, mỗi thuốc đã
// chuyển ra quầy hiện hai dòng.

const doc = (p: string) => readFileSync(new URL(`../${p}`, import.meta.url), "utf8");

type Comp = React.ComponentType<Record<string, unknown>>;

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

const rong = () => null;
const KHO_MOCK = {
  "@/components/ui/ThanhTab": (p: { muc: { nhan: string }[] }) =>
    React.createElement("nav", {}, p.muc.map((m) => React.createElement("i", { key: m.nhan }, `[${m.nhan}]`))),
  "@/components/ui/XuatBangTrongVung": (p: { thanhCongCu: React.ReactNode; children?: React.ReactNode }) =>
    React.createElement("div", {}, p.thanhCongCu, p.children),
  "./InventoryBoard": (p: { batches: { id: string }[]; taiQuay?: boolean }) =>
    React.createElement("table", {}, `bang:${p.taiQuay ? "quay" : "kho"}:${p.batches.map((b) => b.id).join(",")}`),
  "./KiemKeCa": () => React.createElement("p", {}, "kiem-ke-ca"),
  "./ChoGanLo": rong,
  "./ChuyenKho": rong,
  "./DanhMucKho": rong,
  "./KiemKho": rong,
  "./PhieuNhap": rong,
  "./TheoDoiThuoc": rong,
  "./ThuocTraChoKiem": rong,
  "./XuatNhapTon": rong,
  "./ThuocDaXoa": rong,
};

const BATCHES = [lo("k1", "KHO", 10), lo("k2", "KHO", 0), lo("q1", "QUAY", 4), lo("q0", "QUAY", 0)];
const KhoThuoc = nap("app/(dashboard)/pharmacy/inventory/KhoThuoc.tsx", KHO_MOCK);
const ve = (props: Record<string, unknown>) =>
  renderToStaticMarkup(React.createElement(KhoThuoc, { batches: BATCHES, thuoc: [], ...props }));

test("đã tách: tab kho chỉ lô KHO, số trên nút chỉ đếm lô KHO", () => {
  const html = ve({ tachKhoQuay: true, tabDau: "ton" });
  assert.match(html, /\[Thuốc trong kho \(2 lô\)\]/);
  assert.match(html, /bang:kho:k1,k2</);
  assert.doesNotMatch(html, /q1|q0/);
});

test("đã tách: nút Thuốc tại quầy đứng đầu hàng QUẦY, đếm lô quầy còn thuốc, bảng chỉ lô QUẦY còn thuốc", () => {
  const html = ve({ tachKhoQuay: true, tabDau: "thuoc_quay" });
  const nhan = [...html.matchAll(/\[([^\]]+)\]/g)].map((m) => m[1]);
  assert.equal(nhan[0], "Thuốc tại quầy (1 lô còn thuốc)");
  assert.equal(nhan[1], "Kiểm đầu ca");
  // Lô quầy tồn 0 (q0 — lô cũ mặc định ở QUẦY lúc bật tách) KHÔNG hiện; tồn > 0 (q1) hiện.
  assert.match(html, /bang:quay:q1</);
  assert.doesNotMatch(html, /q0/);
  // Bấm khu QUẦY mở tab đầu hàng khi đã tách; chưa tách vẫn mở Kiểm đầu ca.
  assert.match(doc("app/(dashboard)/pharmacy/inventory/KhoThuoc.tsx"), /tachKhoQuay \? "thuoc_quay" : "kiem_dau"/);
});

test("đã tách, quầy chỉ có lô tồn 0: bảng quầy rỗng, nút ghi 0 lô còn thuốc", () => {
  const html = ve({
    tachKhoQuay: true,
    tabDau: "thuoc_quay",
    batches: [lo("k1", "KHO", 10), lo("q0", "QUAY", 0), lo("q00", "QUAY", 0)],
  });
  assert.match(html, /\[Thuốc tại quầy \(0 lô còn thuốc\)\]/);
  assert.match(html, /bang:quay:</);
  assert.doesNotMatch(html, /q0/);
});

test("chưa tách: không có nút quầy, tab kho vẽ đủ mọi lô như cũ; link ?tab=thuoc-quay không vỡ", () => {
  const html = ve({ tachKhoQuay: false, tabDau: "ton" });
  assert.match(html, /\[Thuốc trong kho \(4 lô\)\]/);
  assert.match(html, /bang:kho:k1,k2,q1,q0</);
  const link = ve({ tachKhoQuay: false, tabDau: "thuoc-quay" });
  assert.doesNotMatch(link, /Thuốc tại quầy|bang:/);
  assert.match(link, /kiem-ke-ca/);
});

test("bảng quầy không có [+ Nhập lô] (nhập khi đã tách luôn vào KHO)", () => {
  const Nut = (p: { children?: React.ReactNode }) => React.createElement("button", { type: "button" }, p.children);
  const Board = nap("app/(dashboard)/pharmacy/inventory/InventoryBoard.tsx", {
    "next/navigation": { useRouter: () => ({ refresh() {} }) },
    "@/components/ui/Button": Nut,
    "@/components/ui/Chip": (p: { children?: React.ReactNode }) => React.createElement("span", {}, p.children),
    "../../form-ui": { INPUT: "i", TBL_DIV: "d", TBL_HEAD: "h", TBL_WRAP: "w" },
    "./gui-kho": { guiKho: async () => ({ ok: true }), soKho: String, tienVnd: String },
    "./NhapLo": rong,
  });
  const props = { batches: [], thuoc: [], ghiDuoc: true, tachKhoQuay: true };
  assert.match(renderToStaticMarkup(React.createElement(Board, props)), /\+ Nhập lô/);
  const quay = renderToStaticMarkup(React.createElement(Board, { ...props, taiQuay: true }));
  assert.doesNotMatch(quay, /\+ Nhập lô/);
  assert.match(quay, /Quầy chưa có thuốc — chuyển từ kho sang ở tab Chuyển kho ↔ quầy\./);
});
