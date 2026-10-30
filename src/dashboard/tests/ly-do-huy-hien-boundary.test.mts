// LÝ DO PHẢI HIỆN Ở CHỖ NGƯỜI TA NHÌN (30/10/2026). Nhân sự báo "huỷ lịch không
// có chỗ ghi lý do" — máy chủ ghi đúng, lỗi ở chỗ nhìn: khung khách chỉ in chữ
// tự do, chọn mã mà không gõ chữ là lý do biến mất. Cùng lúc: lý do khách về
// giữa chừng ghi rồi mà không màn nào in; menu ⋯ của dòng lịch vô hình trên iPad.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { chuLyDoHuy } from "../lib/ly-do-huy.ts";

const doc = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");

const khungKhach = doc("../app/(dashboard)/_lam-viec/KhungKhach.tsx");
const chiTietLuot = doc("../app/(dashboard)/reception/checkout/ChiTietLuot.tsx");
const kenhDoiHuy = doc("../app/(dashboard)/customers/KenhDoiHuy.tsx");
const bang = doc("../app/(dashboard)/home/WeeklyAppointmentsTable.tsx");

test("chuLyDoHuy: mã không chữ vẫn có lý do; Khác có chữ chỉ in chữ; dữ liệu cũ in chữ", () => {
  assert.equal(
    chuLyDoHuy("BAO_KHI_NHAC_HEN", null),
    "Đã xác nhận sẽ đến, tới lúc nhắc hẹn thì báo không đến",
  );
  assert.equal(
    chuLyDoHuy("DAT_TRUNG", "  giữ lịch sáng "),
    "Đặt trùng — khách có nhiều lịch, bỏ bớt giữ lại một — giữ lịch sáng",
  );
  assert.equal(chuLyDoHuy("KHAC", "khách chuyển nhà"), "khách chuyển nhà");
  // Dữ liệu cũ (trước khi có mã): chỉ có chữ — in chữ, không lỗi.
  assert.equal(chuLyDoHuy(null, "bận"), "bận");
  // Mã lạ in nguyên mã còn hơn mất.
  assert.equal(chuLyDoHuy("MA_LA", undefined), "MA_LA");
  for (const rong of [
    [null, null],
    [undefined, "   "],
    ["", ""],
  ] as const) {
    assert.equal(chuLyDoHuy(rong[0], rong[1]), null);
  }
});

test("khung khách in lý do qua chuLyDoHuy(mã, chữ), không đọc riêng chữ", () => {
  assert.match(khungKhach, /chuLyDoHuy\(l\.ly_do_huy_ma, l\.ly_do_huy\)/);
  assert.doesNotMatch(khungKhach, /Lý do: \{l\.ly_do_huy\}/);
  // Kênh đổi/huỷ cùng một hàm — không ghép tay bản thứ hai.
  assert.match(kenhDoiHuy, /chuLyDoHuy\(d\.ma, d\.ly_do\)/);
  assert.doesNotMatch(kenhDoiHuy, /\.filter\(Boolean\)\.join\(" — "\)/);
});

test("khách về giữa chừng: lý do hiện cạnh chip ở khung khách và màn Check-out", () => {
  assert.match(khungKhach, /l\.ly_do_ve \? \(/);
  assert.match(khungKhach, /Lý do về: \{l\.ly_do_ve\}/);
  assert.match(chiTietLuot, /<Hang nhan="Lý do về" giaTri=\{d\.ly_do_ve\} \/>/);
});

test("menu ⋯ của dòng lịch luôn hiện trên máy cảm ứng", () => {
  // Ô chứa MenuLich ẩn đến khi rê chuột — máy không rê chuột được phải thấy.
  const i = bang.indexOf("<MenuLich");
  assert.ok(i > 0);
  const o = bang.slice(bang.lastIndexOf("<td", i), i);
  assert.match(o, /opacity-0/);
  assert.match(o, /pointer-coarse:opacity-100/);
  assert.match(o, /max-md:opacity-100/);
});
