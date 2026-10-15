// QUÉT TEM BÁO ĐÚNG LÝ DO (14/10/2026, bấm thật staging): lô nhập "hộp", đơn kê
// "gói" → máy chủ không gợi ý lô (luật cũ), màn từng nói chung chung "Không có
// lô còn bán được…". Nay máy chủ trả `lo_bi_loai`, màn chỉ chọn chữ.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { cauLoKhongDungDuoc, type LoBiLoai } from "../lib/lo-bi-loai.ts";

const doc = (p: string): string => readFileSync(new URL(`../${p}`, import.meta.url), "utf8");

const KHAC_DON_VI: LoBiLoai = {
  drug_batch_id: "lo-1",
  batch_code: "LT00000012",
  ly_do: "KHAC_DON_VI",
  don_vi_lo: "hộp",
  don_vi_ke: "gói",
};
const KHAC_CO_SO: LoBiLoai = {
  drug_batch_id: "lo-2",
  batch_code: "HN-77",
  ly_do: "KHAC_CO_SO",
  don_vi_lo: "viên",
  don_vi_ke: "viên",
};

test("lô khác đơn vị: nói rõ hộp/gói và lối ra (giao không lô / nhờ quản lý chỉnh đơn vị)", () => {
  const cau = cauLoKhongDungDuoc([KHAC_DON_VI, KHAC_CO_SO], "lo-1", "Mirena");
  assert.equal(
    cau,
    "Lô LT00000012 tính theo hộp, đơn kê theo gói — chưa giao theo lô được; giao không lô hoặc nhờ quản lý chỉnh đơn vị.",
  );
});

test("lô khác cơ sở: nói kho cơ sở khác", () => {
  const cau = cauLoKhongDungDuoc([KHAC_DON_VI, KHAC_CO_SO], "lo-2", "Mirena");
  assert.match(cau, /^Lô HN-77 thuộc kho cơ sở khác/);
});

test("đơn vị thiếu / rác không làm hỏng câu", () => {
  const cau = cauLoKhongDungDuoc(
    [{ ...KHAC_DON_VI, don_vi_lo: null, don_vi_ke: "  " }],
    "lo-1",
    "X",
  );
  assert.match(cau, /^Lô LT00000012 tính theo đơn vị khác, đơn kê theo đơn vị khác/);
});

test("không có lý do từ máy chủ → câu chung như cũ (kể cả danh sách thiếu / lô lạ)", () => {
  const chung = "Không có lô còn bán được của Mirena dùng cho dòng đơn này.";
  assert.equal(cauLoKhongDungDuoc(undefined, "lo-1", "Mirena"), chung);
  assert.equal(cauLoKhongDungDuoc([], "lo-1", "Mirena"), chung);
  assert.equal(cauLoKhongDungDuoc([KHAC_DON_VI], "lo-khac", "Mirena"), chung);
  assert.equal(cauLoKhongDungDuoc([KHAC_DON_VI], undefined, "Mirena"), chung);
  assert.equal(
    cauLoKhongDungDuoc([{ ...KHAC_DON_VI, ly_do: "LY_DO_LA" }], "lo-1", "Mirena"),
    chung,
  );
});

test("quầy thuốc: giữ nhánh trang_thai (hết hạn / huỷ / hết tồn / cơ sở khác), thêm câu đúng lý do, không đổi luật chọn lô", () => {
  const b = doc("app/(dashboard)/pharmacy/PharmacyBoard.tsx");
  // Nhánh trạng thái lô ở đầu hàm vẫn còn nguyên.
  assert.match(b, /kq\.lo\.trang_thai !== "ok"/);
  assert.match(b, /NHAN_TRANG_THAI_LO\[kq\.lo\.trang_thai\]/);
  // Lô không nằm trong gợi ý → câu theo lý do máy chủ trả.
  assert.match(
    b,
    /!dong\.lo_goi_y\.some\(\(b\) => b\.drug_batch_id === loId\)[\s\S]{0,400}cauLoKhongDungDuoc\(dong\.lo_bi_loai, loId,/,
  );
  // Luật chọn lô giữ nguyên: lô tem phải ok; mã vuông → lô theo mã hoặc FEFO đầu.
  assert.match(b, /kq\.lo_theo_ma\?\.trang_thai === "ok" \? kq\.lo_theo_ma\.id : kq\.goi_y_lo\[0\]\?\.id/);
  const nhanTrangThai = doc("app/(dashboard)/pharmacy/inventory/OQuetMa.tsx");
  for (const t of ["het_han", "da_huy", "het_ton", "khac_co_so"]) {
    assert.match(nhanTrangThai, new RegExp(`${t}: "`));
  }
});

test("kiểu dòng đơn nhận lo_bi_loai từ máy chủ", () => {
  assert.match(doc("app/(dashboard)/pharmacy/ban-thuoc.ts"), /lo_bi_loai\?: LoBiLoai\[\]/);
});
