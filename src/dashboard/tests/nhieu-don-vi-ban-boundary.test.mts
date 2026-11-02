// Nhiều đơn vị bán (31/10/2026): ô đơn vị dùng chung, quầy chọn đơn vị từng dòng,
// danh mục hiện đủ giá, và không luật nghiệp vụ nào trong TSX.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const doc = (p: string) => readFileSync(new URL(`../${p}`, import.meta.url), "utf8");
const D = "app/(dashboard)";

test("ô đơn vị dùng SearchSelect gõ được, không dùng datalist (hỏng chọn trên iPhone)", () => {
  const o = doc(`${D}/ODonVi.tsx`);
  assert.ok(o.includes("SearchSelect") && o.includes("choGoTu"));
  assert.ok(!o.includes("<datalist"));
  const s = doc(`${D}/SearchSelect.tsx`);
  assert.ok(s.includes("choGoTu") && s.includes("nhanChuGo"), "rời ô là nhận chữ gõ");
});

test("mọi ô đơn vị thuốc đi qua ODonVi", () => {
  for (const tep of [
    `${D}/pharmacy/inventory/DanhMucKho.tsx`,
    `${D}/pharmacy/inventory/SuaDonViBan.tsx`,
    `${D}/pharmacy/inventory/NhapLo.tsx`,
    `${D}/pharmacy/inventory/PhieuNhap.tsx`,
    `${D}/thu-ngan/ChinhDonQuay.tsx`,
    `${D}/_lam-viec/phieu-kham/DonThuocPhieu.tsx`,
  ]) {
    assert.ok(doc(tep).includes("ODonVi"), tep);
  }
});

test("quầy: đổi đơn vị gọi máy chủ, proxy chuyển đúng route", () => {
  const q = doc(`${D}/thu-ngan/ChinhDonQuay.tsx`);
  assert.ok(q.includes('thao_tac: "don-vi"'));
  assert.ok(q.includes("van_de_don_vi") && q.includes("chua_khai_don_vi"));
  assert.ok(doc("app/api/quay-thuoc/route.ts").includes("/api/v1/quay-thuoc/don-vi"));
});

test("không tính giá gợi ý ở TSX: ô trống để máy chủ lưu rõ", () => {
  const s = doc(`${D}/pharmacy/inventory/SuaDonViBan.tsx`);
  assert.ok(s.includes("Trống = hệ số × giá gốc"));
  assert.ok(!/he_so\)?\s*\*/.test(s), "không nhân hệ số trong TSX");
  assert.ok(s.includes("Tắt bán"), "tắt chứ không xoá dòng đã lưu");
});

test("danh mục hiện đủ đơn vị + giá, tồn kèm quy đổi, báo chưa khai đơn vị", () => {
  const d = doc(`${D}/pharmacy/inventory/DanhMucKho.tsx`);
  assert.ok(d.includes("gia_theo_don_vi") && d.includes("ton_quy_doi"));
  assert.ok(d.includes("Chưa khai đơn vị") && d.includes("lo_chua_quy_doi"));
});

test("nhà thuốc: hiện quy đổi, giao theo đơn vị khác, lần giao ghi đơn vị lô", () => {
  const g = doc(`${D}/pharmacy/DongThuoc.tsx`);
  assert.ok(g.includes("dong.quy_doi") && g.includes("da_giao_goc"));
  assert.ok(g.includes("don_vi_giao") && g.includes("x.don_vi"));
});

test("chờ gán lô: hiện số sẽ trừ theo đơn vị lô và việc phải làm", () => {
  const c = doc(`${D}/pharmacy/inventory/ChoGanLo.tsx`);
  assert.ok(c.includes("so_tru") && c.includes("can_lam"));
});
