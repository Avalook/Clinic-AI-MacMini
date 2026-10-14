import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import { runInNewContext } from "node:vm";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

// Màn Nhà thuốc sau contract tiền–thuốc CP4 (19/09/2026). Bốn điều dễ hỏng
// nhất khi ai đó "sửa nhanh" màn này.

const doc = (p: string) => readFileSync(new URL(`../${p}`, import.meta.url), "utf8");
const page = doc("app/(dashboard)/pharmacy/page.tsx");
const board = doc("app/(dashboard)/pharmacy/PharmacyBoard.tsx");
const dong = doc("app/(dashboard)/pharmacy/DongThuoc.tsx");
const kieu = doc("app/(dashboard)/pharmacy/ban-thuoc.ts");
const proxy = doc("app/api/pharmacy/[action]/route.ts");

test("G3a-B: render thật với lối KhoThuoc hiện Sửa/huỷ/hoàn đúng quyền", () => {
  const source = doc("app/(dashboard)/pharmacy/inventory/InventoryBoard.tsx");
  const exports: { default?: React.ComponentType<Record<string, unknown>> } = {};
  const require = createRequire(import.meta.url);
  const code = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
  }).outputText;
  runInNewContext(code, { exports, require: (path: string) => {
    if (path === "next/navigation") return { useRouter: () => ({ refresh() {} }) };
    if (path === "./gui-kho") return { tienVnd: String };
    if (path === "../../form-ui") return {};
    if (path === "@/components/ui/Button") return (p: { children: React.ReactNode }) => React.createElement("button", {}, p.children);
    if (path === "@/components/ui/Chip") return (p: { children: React.ReactNode }) => React.createElement("span", {}, p.children);
    if (path === "./NhapLo") return () => null;
    return require(path);
  } });
  assert.ok(exports.default);
  const props = {
    batches: [{ id: "lo", drug_catalog_id: "thuoc", batch_code: "A", expiry_date: "2020-01-01", quantity_on_hand: 10, unit: "viên", cost_price: null, trang_thai_han: "het_han", canh_bao_han: true, huy_lo_txn_id: "txn", drug: { name_base: "Thuốc" } }],
    thuoc: [], onXemThe() {}, ghiDuoc: true,
  };
  const html = renderToStaticMarkup(React.createElement(exports.default, props));
  assert.match(html, />Sửa lô<\/button>/);
  assert.match(html, />Huỷ lô hết hạn<\/button>/);
  assert.match(html, />Hoàn huỷ lô<\/button>/);
  const readOnly = renderToStaticMarkup(React.createElement(exports.default, {
    ...props, ghiDuoc: false,
  }));
  assert.doesNotMatch(readOnly, /Sửa lô|Huỷ lô hết hạn|Hoàn huỷ lô/);
});

test("G3a: formatter ngày không vẽ epoch hay Invalid Date cho NULL/rác", () => {
  const exports: { fmtNgay?: (iso: string | null) => string } = {};
  const code = ts.transpileModule(kieu, {
    compilerOptions: { module: ts.ModuleKind.CommonJS },
  }).outputText;
  runInNewContext(code, { exports, require: () => ({ VN_TZ: "Asia/Ho_Chi_Minh" }) });
  assert.equal(exports.fmtNgay?.(null), "—");
  assert.equal(exports.fmtNgay?.(""), "—");
  assert.equal(exports.fmtNgay?.("ngày rác"), "—");
  assert.equal(exports.fmtNgay?.("2026-10-14"), "14/10/2026");
});

test("G3a: hai lối nhập không ép hạn, kho nhận NULL và chưa có hạn là chip xám", () => {
  const nhap = doc("app/(dashboard)/pharmacy/inventory/NhapLo.tsx");
  const phieu = doc("app/(dashboard)/pharmacy/inventory/PhieuNhap.tsx");
  const kho = doc("app/(dashboard)/pharmacy/inventory/InventoryBoard.tsx");
  const trangKho = doc("app/(dashboard)/pharmacy/inventory/page.tsx");
  assert.doesNotMatch(nhap, /\|\| !f\.han/);
  assert.doesNotMatch(phieu, /\|\| !d\.han/);
  assert.match(nhap, /expiry_date: f\.han \|\| null/);
  assert.match(kho, /chua_co_han: "neutral"/);
  assert.match(trangKho, /expiry_date: string \| null/);
  assert.doesNotMatch(trangKho, /a\.expiry_date\.localeCompare/);
});

test("G3a: sửa, huỷ hết hạn và hoàn huỷ giữ nút Huỷ cũ và đủ proxy", () => {
  const kho = doc("app/(dashboard)/pharmacy/inventory/InventoryBoard.tsx");
  for (const action of ["sua-lo", "huy-lo-het-han", "hoan-huy-lo"]) {
    assert.match(kho, new RegExp(action));
    assert.match(proxy, new RegExp(`"${action}":`));
  }
  assert.match(kho, /Sửa lô/);
  assert.match(kho, /Huỷ lô hết hạn/);
  assert.match(kho, /loai: "discard"/);
  assert.doesNotMatch(kho, /window\.confirm/);
});

test("màn đọc qua máy chủ, không đọc thẳng Supabase", () => {
  // Giai đoạn tiền thuốc và các nút được phép là luật nghiệp vụ (FastAPI).
  // Bản trước đọc thẳng `prescription` + `drug_batch` rồi tự so tên thuốc.
  assert.match(page, /fetchFromBackend<ManNhaThuoc>\("\/api\/v1\/pharmacy\/ban-thuoc"\)/);
  assert.doesNotMatch(page, /getSupabaseServer|\.from\(/);
});

test("nút hiện theo lời máy chủ, không tự suy từ giai đoạn", () => {
  // Mã giai đoạn chỉ được dùng để tra NHÃN (ban-thuoc.ts). Component nào so
  // `giai_doan === "..."` để quyết nút là đang chép lại luật của máy chủ.
  for (const src of [board, dong]) {
    assert.doesNotMatch(src, /===\s*"(CHUA_SAN_SANG|SAN_SANG|CHO_XAC_MINH|DA_THU|CAN_DOI_SOAT|DA_THU_CU)"/);
  }
  for (const nut of ["chon_lo", "xac_dinh_thuoc", "khai_so_mua", "tu_choi", "chot", "giao_luong_cu"]) {
    assert.match(dong, new RegExp(`tt\\.${nut}`), `thiếu cổng tt.${nut}`);
  }
  for (const nut of ["bo", "doi", "giao"]) {
    assert.match(dong, new RegExp(`p\\.thao_tac\\.${nut}`), `thiếu cổng p.thao_tac.${nut}`);
  }
});

test("không gọi số hệ thống là 'tồn khả dụng' (HOLD J6)", () => {
  // Tên chính thức của con số chống bán trùng chưa chốt với kho.
  for (const src of [board, dong, kieu]) {
    assert.doesNotMatch(src, /tồn khả dụng/i);
  }
  assert.match(dong, /Tồn vật lý/);
  assert.match(dong, /Có thể phân lô lúc này/);
});

test("proxy mở đủ và chỉ đúng các thao tác phân lô của máy chủ", () => {
  for (const [a, p] of [
    ["xac-dinh-thuoc", "xac-dinh-thuoc"],
    ["so-luong-mua", "so-luong-mua"],
    ["phan-lo", "phan-lo"],
    ["bo-phan-lo", "bo-phan-lo"],
    ["doi-lo", "doi-lo"],
  ]) {
    assert.match(proxy, new RegExp(`"${a}":\\s*"/api/v1/pharmacy/${p}"`));
  }
  assert.doesNotMatch(dong, /window\.confirm/);
});

// ── CP5: hoàn tiền / huỷ phần chưa giao / khách trả thuốc ─────────────────
const hoan = doc("app/(dashboard)/thu-ngan/HoanTien.tsx");
const payProxy = doc("app/api/payment/route.ts");

test("CP5: màn hoàn tiền không tự tính tiền và chỉ hiện nút khi máy chủ cho", () => {
  // Số tiền hoàn do máy chủ tính theo đơn giá ảnh chụp — màn không nhân.
  assert.doesNotMatch(hoan, /don_gia/);
  assert.doesNotMatch(hoan, /\*\s*Number|Number\([^)]*\)\s*\*/);
  // Nút ghi chỉ khi máy chủ báo có quyền hoàn (tạm thời chỉ Quản lý, HOLD J4).
  assert.match(hoan, /coQuyenHoan && k\.status === "PENDING"/);
  assert.match(hoan, /coQuyenHoan && conHoan\.length > 0/);
  assert.doesNotMatch(hoan, /window\.confirm/);
  for (const a of ["hoan-tien", "hoan-tien-xac-nhan", "hoan-tien-dong"]) {
    assert.match(payProxy, new RegExp(`p\\.action === "${a}"`));
  }
});

test("CP5: khách trả / huỷ phần chưa giao theo cờ máy chủ, đủ proxy", () => {
  assert.match(dong, /x\.thao_tac\.tra/);
  assert.match(dong, /tt\.huy_chua_giao/);
  for (const [a, p] of [
    ["huy-phan-chua-giao", "huy-phan-chua-giao"],
    ["khach-tra", "khach-tra"],
  ]) {
    assert.match(proxy, new RegExp(`"${a}":\\s*"/api/v1/pharmacy/${p}"`));
  }
  // Khách trả KHÔNG có nút "đưa lại bán / huỷ / cách ly" (HOLD J1/J2).
  assert.doesNotMatch(dong, /disposition|Đưa lại bán|Nhập lại kho/);
});
