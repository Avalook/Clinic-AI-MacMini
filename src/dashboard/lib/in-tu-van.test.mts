// Mục A bản in phiếu khám: chữ bác sĩ tư vấn ghi phải lên giấy (18/11/2026 —
// trước đó chỉ in ô "Ghi chú bổ sung", khách có khách không).
import assert from "node:assert/strict";
import test from "node:test";

import { ghiChuTuVanIn } from "./in-tu-van.ts";
import type { DauPhieu, ONhap } from "./phieu-kham.ts";

const MUC_A = { block: [{ ma: "nt_a_note" }] } as Parameters<typeof ghiChuTuVanIn>[1];
const tv = (...noiDung: string[]): DauPhieu["tu_van"] =>
  noiDung.map((n, i) => ({ noi_dung: n, luc: `2026-11-16T12:0${i}:00Z`, vong: 0 }));
const o = (gia_tri: unknown): ONhap => ({ gia_tri, nguon: "USER" }) as ONhap;

test("có ghi chú tư vấn, ô Ghi chú bổ sung trống → in ghi chú tư vấn", () => {
  assert.deepEqual(ghiChuTuVanIn(tv("Kinh nguyệt đều\nNgủ ít"), MUC_A, {}), [
    "Kinh nguyệt đều\nNgủ ít",
  ]);
});

test("ghi chú tư vấn giống hệt ô đã gõ (khác khoảng trắng hai đầu) → không in lặp", () => {
  const duLieu = { nt_a_note: o("Kinh nguyệt đều  ") };
  assert.deepEqual(ghiChuTuVanIn(tv(" Kinh nguyệt đều"), MUC_A, duLieu), []);
});

test("khác dù một chữ → in cả ghi chú tư vấn", () => {
  const duLieu = { nt_a_note: o("Nên soi cổ tử cung") };
  assert.deepEqual(ghiChuTuVanIn(tv("Nên soi cổ tử cung."), MUC_A, duLieu), [
    "Nên soi cổ tử cung.",
  ]);
});

test("đoạn trống / chỉ khoảng trắng không in; nhiều phiên giữ đúng thứ tự", () => {
  assert.deepEqual(ghiChuTuVanIn(tv("Phiên 1", "   ", "", "Phiên 2"), MUC_A, {}), [
    "Phiên 1",
    "Phiên 2",
  ]);
});

test("rác: không có dữ liệu đầu phiếu / ô không phải chữ → không ném", () => {
  assert.deepEqual(ghiChuTuVanIn(undefined, MUC_A, {}), []);
  assert.deepEqual(ghiChuTuVanIn(tv("A"), MUC_A, { nt_a_note: o(["A"]) }), ["A"]);
  assert.deepEqual(ghiChuTuVanIn(tv("A"), MUC_A, { nt_a_note: o(null) }), ["A"]);
});
