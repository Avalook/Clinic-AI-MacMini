import assert from "node:assert/strict";
import test from "node:test";

import { nhanDaTra, nhanDoiLieuTrinh, nhanNutHoanTac } from "../lib/lieu-trinh.ts";

// CHỮ LIỆU TRÌNH (bấm thử staging 09/10/2026): các câu cũ sai ngữ cảnh —
// "Hoàn tác hoàn tác", "Đã trả 2 buổi · còn nợ 3/6" (thực trả 3), lịch sử
// "6 → 6 buổi" cho Dừng / Hoàn tác.

test("nhanDaTra gộp buổi lẻ + trả trước để khớp 'còn nợ'", () => {
  assert.equal(nhanDaTra(0, 0), "chưa trả buổi nào");
  assert.equal(nhanDaTra(2, 1), "đã trả 3 buổi (1 lẻ + 2 trả trước)");
  assert.equal(nhanDaTra(2), "đã trả trước 2 buổi");
  assert.equal(nhanDaTra(0, 1), "đã trả 1 buổi (trả lẻ)");
});

test("nhanNutHoanTac: hoàn tác một lần hoàn tác là 'Làm lại', không lặp chữ", () => {
  assert.equal(nhanNutHoanTac("HOAN_TAC"), "Làm lại thao tác vừa hoàn tác");
  assert.equal(nhanNutHoanTac("DUNG"), "Hoàn tác dừng");
  assert.equal(nhanNutHoanTac("DIEU_CHINH"), "Hoàn tác điều chỉnh");
  assert.equal(nhanNutHoanTac(null), "Hoàn tác");
  assert.equal(nhanNutHoanTac("LA"), "Hoàn tác");
});

test("nhanDoiLieuTrinh chỉ ghi phần đổi thật", () => {
  const cu = { so_buoi: 6, trang_thai: "DANG_LAM", ghi_chu_lo_trinh: "2 buổi/tuần" };
  assert.equal(nhanDoiLieuTrinh(cu, { ...cu, trang_thai: "DUNG" }), "Đang làm → Dừng");
  assert.equal(nhanDoiLieuTrinh(cu, { ...cu, so_buoi: 8 }), "6 → 8 buổi");
  assert.equal(nhanDoiLieuTrinh(cu, { ...cu, ghi_chu_lo_trinh: "3 buổi/tuần" }), "đổi ghi chú lộ trình");
  assert.equal(nhanDoiLieuTrinh(cu, { ...cu }), "");
  assert.equal(nhanDoiLieuTrinh(null, { so_buoi: 5, trang_thai: "DE_XUAT" }), "— → 5 buổi");
  assert.equal(nhanDoiLieuTrinh(cu, null), "");
  assert.doesNotMatch(nhanDoiLieuTrinh(cu, { ...cu, trang_thai: "DUNG" }), /6 → 6/);
});
