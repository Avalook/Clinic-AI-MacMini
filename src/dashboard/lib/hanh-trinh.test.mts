import assert from "node:assert/strict";
import test from "node:test";

import {
  doanNoi,
  gioMoc,
  khoang,
  phutDichVu,
  type DichVuHanhTrinh,
  type MocMayChu,
} from "./hanh-trinh.ts";

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

// --- Bảng "Từng dịch vụ" (27/09/2026) ---------------------------------------
const dv = (
  tt: DichVuHanhTrinh["trang_thai"],
  gui: number,
  thu: number | null,
  batDau: number | null,
  xong: number | null,
): DichVuHanhTrinh => ({
  id: "o1",
  ten: "Siêu âm",
  lan: 1,
  noi: "Phòng siêu âm",
  trang_thai: tt,
  gui: luc(gui),
  thu: thu == null ? null : luc(thu),
  bat_dau: batDau == null ? null : luc(batDau),
  xong: xong == null ? null : luc(xong),
});
const bayGio = (phut: number) => new Date(luc(phut)).getTime();

test("dịch vụ đã xong: chờ từ lúc thu tới lúc bắt đầu, làm tới lúc xong", () => {
  const p = phutDichVu(dv("XONG", 40, 45, 60, 80), bayGio(200));
  assert.equal(p.moc, "Gửi 08:40 · Thu 08:45 · Bắt đầu 09:00 · Xong 09:20");
  assert.deepEqual([p.cho, p.lam, p.tong, p.dangChay], [15, 20, 40, false]);
});

test("đang làm và đang chờ nhích theo đồng hồ", () => {
  const dang = phutDichVu(dv("DANG_LAM", 40, 45, 60, null), bayGio(72));
  assert.deepEqual([dang.cho, dang.lam, dang.tong, dang.dangChay], [15, 12, 32, true]);
  const cho = phutDichVu(dv("CHO_LAM", 40, 50, null, null), bayGio(58));
  assert.deepEqual([cho.cho, cho.lam, cho.tong], [8, null, 18]);
  // Chưa thu: chờ tính từ lúc gửi.
  const chuaThu = phutDichVu(dv("CHO_THU", 40, null, null, null), bayGio(47));
  assert.equal(chuaThu.cho, 7);
  assert.equal(chuaThu.moc, "Gửi 08:40");
});

test("khách bỏ không đếm giờ; giờ lệch không ra số âm", () => {
  const bo = phutDichVu(dv("BO", 40, null, null, null), bayGio(90));
  assert.deepEqual([bo.cho, bo.lam, bo.tong, bo.dangChay], [null, null, null, false]);
  const lech = phutDichVu(dv("CHO_THU", 40, null, null, null), bayGio(39));
  assert.equal(lech.cho, 0);
  assert.equal(lech.tong, 0);
  // Xong mà không có giờ bắt đầu (dịch vụ không qua bước bắt đầu): không bịa giờ chờ.
  const khongBatDau = phutDichVu(dv("XONG", 40, 45, null, 70), bayGio(100));
  assert.deepEqual([khongBatDau.cho, khongBatDau.lam, khongBatDau.tong], [null, null, 30]);
});
