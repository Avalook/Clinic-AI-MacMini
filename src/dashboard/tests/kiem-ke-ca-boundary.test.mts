import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import { runInNewContext } from "node:vm";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

// Kiểm kê đầu / cuối ca ở quầy + cột tồn của Báo cáo hàng hoá (G6, 14/10/2026):
// màn chỉ vẽ + gửi lệnh, luật ở máy chủ.

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
    fetch: () => new Promise(() => {}),
    require: (p: string) => (p in mock ? mock[p] : require(p)),
  });
  assert.ok(exports.default, `không nạp được ${duongDan}`);
  return exports.default;
}

const Nut = (p: { children?: React.ReactNode }) => React.createElement("button", { type: "button" }, p.children);
const Chip = (p: { children?: React.ReactNode }) => React.createElement("span", {}, p.children);
const MOCK = {
  "@/components/ui/Button": Nut,
  "@/components/ui/Chip": Chip,
  "@/components/ui/XacNhanTaiCho": (p: { cau?: string }) => React.createElement("div", { role: "alertdialog" }, p.cau),
  "../../form-ui": { INPUT: "i", TBL_DIV: "d", TBL_HEAD: "h", TBL_WRAP: "w" },
  "./gui-kho": { soKho: (n: unknown) => String(n ?? 0) },
};

test("proxy kiểm kê: danh sách trắng bước ghi, id phải là uuid, không có đường lạ", () => {
  const buoc = doc("app/api/pharmacy/kiem-ke-ca/[id]/[buoc]/route.ts");
  for (const b of ["dem", "dung-so-cuoi-ca-truoc", "chot", "dieu-chinh", "hoan-tac-dieu-chinh", "sua-so-dem"]) {
    assert.match(buoc, new RegExp(`"${b}"`));
  }
  assert.match(buoc, /UUID_RE\.test\(id\)/);
  assert.match(buoc, /BUOC\.has\(buoc\)/);
  assert.match(doc("app/api/pharmacy/kiem-ke-ca/[id]/route.ts"), /UUID_RE\.test\(id\)/);
  assert.match(doc("app/api/pharmacy/kiem-ke-ca/route.ts"), /\/api\/v1\/pharmacy\/kiem-ke-ca/);
});

test("Quầy có hai tab Kiểm đầu ca / Kiểm cuối ca; bảng realtime nghe kiem_ke_ca", () => {
  const kho = doc("app/(dashboard)/pharmacy/inventory/KhoThuoc.tsx");
  assert.match(kho, /ma: "kiem_dau" as const, nhan: "Kiểm đầu ca"/);
  assert.match(kho, /ma: "kiem_cuoi" as const, nhan: "Kiểm cuối ca"/);
  assert.match(kho, /loaiCoDinh="DAU"/);
  assert.match(kho, /loaiCoDinh="CUOI"/);
  assert.match(doc("app/(dashboard)/RealtimeRefresher.tsx"), /"kiem_ke_ca",/);
});

test("KiemKeCa: người không có quyền ghi chỉ xem — không nút mở phiếu", () => {
  const Kiem = nap("app/(dashboard)/pharmacy/inventory/KiemKeCa.tsx", MOCK);
  const batches = [
    {
      id: "b1",
      drug_catalog_id: "t1",
      batch_code: "L1",
      unit: "viên",
      noi_chua: "QUAY",
      quantity_on_hand: 5,
      drug: { name_base: "Para", name_raw: "Para", variant: null },
    },
  ];
  const ghi = renderToStaticMarkup(React.createElement(Kiem, { batches, ghiDuoc: true }));
  assert.match(ghi, />Bắt đầu kiểm kê<\/button>/);
  const xem = renderToStaticMarkup(React.createElement(Kiem, { batches, ghiDuoc: false }));
  assert.doesNotMatch(xem, />Bắt đầu kiểm kê<\/button>/);
  assert.doesNotMatch(doc("app/(dashboard)/pharmacy/inventory/KiemKeCa.tsx"), /window\.confirm/);
});

test("Chốt kiểm kê phải qua xác nhận TẠI CHỖ (XacNhanTaiCho), nút Chốt không gọi chốt ngay", () => {
  const nguon = doc("app/(dashboard)/pharmacy/inventory/KiemKeCa.tsx");
  assert.match(nguon, /import XacNhanTaiCho from "@\/components\/ui\/XacNhanTaiCho"/);
  assert.match(nguon, /Chốt kiểm kê\? Hệ thống lưu số đếm và chênh lệch\./);
  assert.match(nguon, /nhanDongY="Chốt"/);
  // Nút "Chốt kiểm kê" chỉ mở câu hỏi; chỉ [Chốt] trong dải mới gọi chot().
  assert.match(nguon, /onClick=\{\(\) => setHoiChot\(phieu\.id\)\}/);
  assert.doesNotMatch(nguon, /onClick=\{\(\) => void chot\(\)\}/);
  assert.match(nguon, /onDongY=\{\(\) => \{\s*setHoiChot\(null\);\s*void chot\(\);\s*\}\}/);
  assert.match(nguon, /onThoi=\{\(\) => setHoiChot\(null\)\}/);
  assert.doesNotMatch(nguon, /window\.confirm/);
});

test("Kiểm đầu/cuối ca: tìm từng thuốc, giữ số đã nhập khi lọc, bỏ hướng dẫn thừa", () => {
  const kiem = doc("app/(dashboard)/pharmacy/inventory/KiemKeCa.tsx");
  assert.match(kiem, /aria-label="Tìm thuốc cần kiểm kê"/);
  assert.match(kiem, /const hangHien = hang\.filter/);
  assert.match(kiem, /normalize\("NFD"\)/);
  assert.match(kiem, /const gui = dong\s*\.filter/);
  assert.match(kiem, /Đã đếm/);
  assert.match(kiem, /hangHien\.map/);
  assert.doesNotMatch(kiem, /Đếm số thuốc thực tế trên kệ quầy/);
  assert.doesNotMatch(kiem, /Nhắc \(không chặn bán\)/);
  assert.doesNotMatch(kiem, /Bấm một lần kiểm kê để xem hoặc nhập tiếp/);
  assert.doesNotMatch(kiem, /Chưa có phiếu nào/);
});

test("Kho thuốc: lọc mã lô và các nhãn nói rõ nghĩa", () => {
  const ton = doc("app/(dashboard)/pharmacy/inventory/InventoryBoard.tsx");
  const nhap = doc("app/(dashboard)/pharmacy/inventory/PhieuNhap.tsx");
  const dm = doc("app/(dashboard)/pharmacy/inventory/DanhMucKho.tsx");
  const gan = doc("app/(dashboard)/pharmacy/inventory/ChoGanLo.tsx");
  const baoCao = doc("app/(dashboard)/pharmacy/inventory/XuatNhapTon.tsx");
  assert.match(ton, /aria-label="Lọc tồn kho theo tên thuốc hoặc mã lô"/);
  assert.match(ton, /placeholder="Nhập tên thuốc hoặc mã lô/);
  assert.match(nhap, /Thêm thuốc vào phiếu nhập/);
  assert.match(dm, /Thông tin thuốc cần kiểm tra/);
  assert.match(gan, /SL đã giao cho khách/);
  assert.doesNotMatch(baoCao, /Các cột nghĩa là gì/);
});

const dong = (kho: unknown) => ({
  ma: "SP1",
  ten: "Para",
  don_vi: "viên",
  khoa: "t1",
  sl_ban: 10,
  doanh_thu: 100000,
  sl_tra: 0,
  gia_tri_tra: 0,
  doanh_thu_thuan: 100000,
  kho,
});

test("Báo cáo hàng hoá: cột tồn ĐÚNG THỨ TỰ khách chốt; không có khối kho thì khuôn cũ", () => {
  const Bang = nap("app/(dashboard)/reports/BangHangHoa.tsx", {});
  const tong = { so_mat_hang: 1, sl_ban: 10, doanh_thu: 100000, sl_tra: 0, gia_tri_tra: 0, doanh_thu_thuan: 100000 };
  const moi = renderToStaticMarkup(
    React.createElement(Bang, {
      hh: {
        co_ton: true,
        tong,
        dong: [
          dong({
            giao_chua_gan_lo: null,
            theo_don_vi: [
              { don_vi: "viên", ton_dau: 20, nhap: 5, sl_ban: 4, sl_tra: 1, khac: 0, ton_cuoi: 22, kiem_ke: 21, lech: -1, da_thu_chua_giao: 6 },
            ],
          }),
        ],
      },
    }),
  );
  const cot = [...moi.matchAll(/<th[^>]*>([^<]*)<\/th>/g)].map((m) => m[1]);
  assert.deepEqual(cot, [
    "Mã hàng", "Tên hàng", "Tồn đầu", "Nhập trong ca", "SL bán", "SL trả", "Tồn cuối ca",
    "Kiểm kê", "Lệch", "Đã thu chưa giao", "Doanh thu", "GT trả", "Doanh thu thuần",
  ]);
  assert.match(moi, /-1/); // lệch hiện
  assert.match(moi, /21/); // kiểm kê hiện
  const cu = renderToStaticMarkup(React.createElement(Bang, { hh: { tong, dong: [dong(undefined)] } }));
  assert.doesNotMatch(cu, /Tồn đầu/);
  assert.match(cu, /SL Bán/);
});

test("Báo cáo hàng hoá: chưa kiểm cuối ca thì Kiểm kê / Lệch là '—', không suy ra", () => {
  const Bang = nap("app/(dashboard)/reports/BangHangHoa.tsx", {});
  const html = renderToStaticMarkup(
    React.createElement(Bang, {
      hh: {
        co_ton: true,
        tong: { so_mat_hang: 1, sl_ban: 0, doanh_thu: 0, sl_tra: 0, gia_tri_tra: 0, doanh_thu_thuan: 0 },
        dong: [
          dong({
            giao_chua_gan_lo: 3,
            theo_don_vi: [
              { don_vi: "viên", ton_dau: 1, nhap: 0, sl_ban: 0, sl_tra: 0, khac: 2, ton_cuoi: 3, kiem_ke: null, lech: null, da_thu_chua_giao: 0 },
            ],
          }),
        ],
      },
    }),
  );
  assert.match(html, /Đã giao chưa gắn lô: 3/);
  assert.match(html, /gồm ±điều chỉnh\/huỷ/);
  assert.equal([...html.matchAll(/<span class="block whitespace-nowrap">—<\/span>/g)].length >= 2, true);
});
