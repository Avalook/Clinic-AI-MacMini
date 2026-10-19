import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// Lô cũ lệch đơn vị: màn bán nói rõ hệ quả thay vì "kho chưa có lô".
// Nhập mới dùng QuyDoiNhap để đổi về đơn vị bán, không hiện cảnh báo nhập cũ.
// (Mảng/đối tượng từ vm khác realm nên so bằng chuỗi.)

const doc = (p: string) => readFileSync(new URL(`../${p}`, import.meta.url), "utf8");

type LoBiLoai = {
  drug_batch_id: string;
  batch_code: string;
  ly_do: string;
  don_vi_lo: string | null;
  don_vi_ke: string | null;
};

function napLib(): {
  cauKhoCoLoKhacDonVi: (lo: LoBiLoai[] | undefined, ten: string) => string | null;
  canhBaoNhapKhacDonViBan: (nhap: string | null | undefined, ban: string | null | undefined) => string | null;
} {
  const exports: Record<string, unknown> = {};
  const code = ts.transpileModule(doc("lib/lo-bi-loai.ts"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  runInNewContext(code, { exports, Set });
  return exports as ReturnType<typeof napLib>;
}

const lo = (don_vi_lo: string | null, ly_do = "KHAC_DON_VI"): LoBiLoai => ({
  drug_batch_id: "x",
  batch_code: "AG-1",
  ly_do,
  don_vi_lo,
  don_vi_ke: "gói",
});

test("màn bán: kho có lô khác đơn vị → câu nói rõ kho không tự trừ", () => {
  const { cauKhoCoLoKhacDonVi } = napLib();
  const cau = cauKhoCoLoKhacDonVi([lo("hộp")], "Androgel 1% gói");
  assert.ok(cau);
  assert.match(cau, /Kho có Androgel 1% gói nhưng tính theo hộp, còn đơn này theo gói/);
  assert.match(cau, /KHÔNG tự trừ/);
  assert.match(cau, /Nhập lô theo gói hoặc báo quản lý/);
});

test("màn bán: nhiều lô cùng đơn vị chỉ nêu một lần; lô khác cơ sở không tính", () => {
  const { cauKhoCoLoKhacDonVi } = napLib();
  const cau = cauKhoCoLoKhacDonVi([lo("hộp"), lo("hộp"), lo("vỉ")], "X");
  assert.ok(cau?.includes("tính theo hộp, vỉ,"));
  assert.equal(cauKhoCoLoKhacDonVi([lo("hộp", "KHAC_CO_SO")], "X"), null);
  assert.equal(cauKhoCoLoKhacDonVi([], "X"), null);
  assert.equal(cauKhoCoLoKhacDonVi(undefined, "X"), null);
});

test("nhập: đơn vị nhập khác đơn vị bán thì cảnh báo, khác cách viết thì không", () => {
  const { canhBaoNhapKhacDonViBan } = napLib();
  const cau = canhBaoNhapKhacDonViBan("hộp", "gói");
  assert.ok(cau);
  assert.match(cau, /bán theo “gói”, nhập theo “hộp”/);
  assert.match(cau, /KHÔNG tự trừ/);
  assert.equal(canhBaoNhapKhacDonViBan(" Gói ", "gói"), null);
  assert.equal(canhBaoNhapKhacDonViBan("", "gói"), null);
  assert.equal(canhBaoNhapKhacDonViBan("hộp", null), null);
  assert.equal(canhBaoNhapKhacDonViBan(undefined, undefined), null);
});

test("màn bán giải thích lô cũ; màn nhập dùng quy đổi, không hiện cảnh báo cũ", () => {
  const dongThuoc = doc("app/(dashboard)/pharmacy/DongThuoc.tsx");
  assert.match(dongThuoc, /cauKhoCoLoKhacDonVi\(\s*dong\.lo_bi_loai/);
  assert.ok(dongThuoc.includes("Kho chưa có lô cho thuốc này"), "câu cũ vẫn là mặc định");
  for (const f of ["NhapLo", "PhieuNhap"]) {
    const s = doc(`app/(dashboard)/pharmacy/inventory/${f}.tsx`);
    assert.ok(!s.includes("canhBaoNhapKhacDonViBan"), `${f} còn gắn cảnh báo nhập cũ`);
    assert.match(s, /import QuyDoiNhap from "\.\/QuyDoiNhap"/, `${f} thiếu ô quy đổi`);
    assert.match(s, /<QuyDoiNhap\s/, `${f} chưa hiển thị ô quy đổi`);
    assert.ok(s.includes("he_so:"), `${f} không gửi hệ số quy đổi`);
    assert.ok(s.includes("xac_nhan_he_so:"), `${f} không gửi xác nhận hệ số`);
  }
  const cho = doc("app/(dashboard)/pharmacy/inventory/ChoGanLo.tsx");
  assert.ok(cho.includes("lo_khac_don_vi") && cho.includes("khác đơn vị nên không gắn được"));
  // Điện thoại: cột Khách / Giao lúc ẩn để cột Gán lô (nói lý do) nằm trong màn hình.
  assert.ok(cho.includes('hidden px-3 py-2 sm:table-cell">Khách'));
  assert.ok(cho.includes('hidden px-3 py-2 sm:table-cell">Giao lúc'));
  assert.ok(cho.includes("sm:min-w-2xl"));
});

test("bảng lô thuốc trên điện thoại: Mã lô và Giá nhập ẩn, mã lô hiện dưới tên thuốc", () => {
  const b = doc("app/(dashboard)/pharmacy/inventory/InventoryBoard.tsx");
  assert.ok(b.includes('sm:min-w-2xl'), "bảng chỉ ép rộng từ cỡ sm");
  assert.ok(b.includes('hidden px-3 py-2 sm:table-cell">Mã lô'));
  assert.ok(b.includes("sm:table-cell\">Giá nhập"));
  assert.ok(b.includes("block text-meta font-normal text-ink-muted sm:hidden"));
});
