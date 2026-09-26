import assert from "node:assert/strict";
import test from "node:test";

import { doanNoi, gioMoc, khoang, type MocMayChu } from "./hanh-trinh.ts";

// 08:00 giờ VN = 01:00 UTC.
const luc = (phut: number) => new Date(Date.UTC(2026, 8, 26, 1, phut)).toISOString();
const moc = (ma: string, bat: number | null, ket: number | null, tt: MocMayChu["trang_thai"]): MocMayChu => ({
  ma,
  ten: ma,
  noi: "",
  bat: bat == null ? null : luc(bat),
  ket: ket == null ? null : luc(ket),
  trang_thai: tt,
});

test("khoang đọc như người nói", () => {
  assert.equal(khoang(7), "7 phút");
  assert.equal(khoang(65), "1 giờ 5 phút");
  assert.equal(khoang(120), "2 giờ");
  assert.equal(khoang(-3), "0 phút");
});

test("đoạn giữa hai mốc đã có = khoảng chờ từ lúc xong tới lúc mốc sau bắt đầu", () => {
  const d = doanNoi(
    [moc("CHECK_IN", 0, 0, "xong"), moc("SINH_HIEU", 10, 14, "xong"), moc("KHAM", 30, null, "dang"), moc("VE", null, null, "chua")],
    new Date(luc(42)).getTime(),
  );
  assert.deepEqual(d[0], { nhan: "10 phút", trangThai: "xong" });
  assert.deepEqual(d[1], { nhan: "16 phút", trangThai: "xong" });
  // Mốc gần nhất đã bắt đầu, chưa xong: đoạn sau nó đang chạy.
  assert.deepEqual(d[2], { nhan: "đang 12 phút", trangThai: "dang" });
});

test("mốc gần nhất đã xong mà mốc sau chưa tới: chờ", () => {
  const d = doanNoi([moc("SINH_HIEU", 10, 14, "xong"), moc("KHAM", null, null, "chua")], new Date(luc(20)).getTime());
  assert.deepEqual(d[0], { nhan: "chờ 6 phút", trangThai: "dang" });
});

test("đặt lịch hôm trước ghi 'hôm trước', không tính khoảng qua đêm", () => {
  const m = { ...moc("DAT_LICH", -1500, -1500, "xong"), hom_truoc: true };
  const d = doanNoi([m, moc("CHECK_IN", 0, 0, "xong")], new Date(luc(5)).getTime());
  assert.deepEqual(d[0], { nhan: "hôm trước", trangThai: "xong" });
  assert.match(gioMoc(m), /25/, "mốc hôm trước ghi cả ngày");
});

test("gửi chỉ định nhiều lần: một mốc, ghi từng lần", () => {
  const m: MocMayChu = {
    ...moc("CHI_DINH", 40, 80, "xong"),
    cac_lan: [
      { lan: 1, luc: luc(40), so: 2 },
      { lan: 2, luc: luc(80), so: 1 },
    ],
  };
  assert.equal(gioMoc(m), "Lần 1 08:40 · Lần 2 09:20");
  assert.equal(gioMoc(moc("TU_VAN", 20, 35, "xong")), "08:20 → 08:35");
});
