import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

// Kho ↔ quầy thật (31/10/2026): nút do máy chủ quyết, câu hoàn tác không hiện nguyên
// tổng phiếu, mọi đường mới nằm trong danh sách trắng của proxy.

const doc = (p: string) => readFileSync(join(process.cwd(), p), "utf8");
const proxy = doc("app/api/pharmacy/[action]/route.ts");
const guiKho = doc("app/(dashboard)/pharmacy/inventory/gui-kho.ts");

test("proxy và gui-kho khai đủ lệnh ghi mới", () => {
  for (const a of ["huy-cho-gan-lo", "hoan-tac-kiem-kho", "sua-so-kiem-ke"]) {
    assert.match(proxy, new RegExp(`"${a}": "/api/v1/pharmacy/${a}"`));
    assert.match(guiKho, new RegExp(`"${a}"`));
  }
  assert.match(proxy, /"hoan-tac-giao": "\/api\/v1\/pharmacy\/hoan-tac-giao"/);
  assert.match(proxy, /"lech-kiem-ke":/);
  assert.match(proxy, /lech-kiem-ke-xlsx/);
});

test("NutHoanTac: số phải trả do máy chủ tính, không nhận tổng phiếu từ màn", () => {
  const nut = doc("app/(dashboard)/thu-ngan/NutHoanTac.tsx");
  assert.match(nut, /api\/payment\?hoanTac=/);
  assert.match(nut, /phai_tra/);
  assert.doesNotMatch(nut, /soTien/);
  for (const p of ["GiaoDich", "LichSuThu", "QuayThuNgan"]) {
    const src = doc(`app/(dashboard)/thu-ngan/${p}.tsx`);
    assert.doesNotMatch(src, /<NutHoanTac[^>]*soTien/);
  }
});

test("DongThuoc: nút Hoàn tác giao do máy chủ quyết, có hỏi tại chỗ", () => {
  const dong = doc("app/(dashboard)/pharmacy/DongThuoc.tsx");
  assert.match(dong, /x\.thao_tac\.hoan_tac_giao/);
  assert.match(dong, /goi\("hoan-tac-giao"/);
  assert.match(dong, /goi\("huy-cho-gan-lo"/);
  assert.match(dong, /XacNhanTaiCho/);
});

test("Quầy → Kho bắt lý do trên màn; nút bật tách lấy trạng thái máy chủ vừa trả", () => {
  const ck = doc("app/(dashboard)/pharmacy/inventory/ChuyenKho.tsx");
  assert.match(ck, /huong === "QUAY_KHO" && !lyDo\.trim\(\)/);
  assert.match(ck, /setTachVuaDoi/);
});

test("Báo cáo kho có khối Lệch kiểm kê; nút Sửa số do máy chủ quyết", () => {
  const bc = doc("app/(dashboard)/pharmacy/inventory/XuatNhapTon.tsx");
  assert.match(bc, /<LechKiemKe tu=\{k\.tu\} den=\{k\.den\} \/>/);
  const lech = doc("app/(dashboard)/pharmacy/inventory/LechKiemKe.tsx");
  assert.match(lech, /d\.thao_tac\.sua/);
  assert.match(lech, /Xuất Excel lệch/);
});
