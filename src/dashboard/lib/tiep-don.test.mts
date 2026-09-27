import assert from "node:assert/strict";
import test from "node:test";

import {
  chuanHoa,
  dongPhu,
  locTiepDon,
  toneTrangThai,
  type BuoiTiepDon,
  type DongTiepDon,
} from "./tiep-don.ts";

function dong(p: Partial<DongTiepDon> & { nhom?: DongTiepDon["trang_thai"]["nhom"] }): DongTiepDon {
  const { nhom = "chua_den", ...rest } = p;
  return {
    appointment_id: "a",
    visit_id: null,
    clinic_patient_id: null,
    ten: "Bùi Minh Nga",
    ma_khach: "BN-2026-001",
    sdt: "0900001237",
    so_booking: 5,
    so_tiep_don: null,
    gio_hen: "07:30",
    loai_kham: "Hiếm muộn",
    bac_si: null,
    loai_khach: null,
    uu_tien: false,
    uu_tien_ly_do: null,
    trang_thai: { loai: "cho", nhan: "Chưa đến", nhom },
    check_in_duoc: nhom === "chua_den",
    check_out_duoc: false,
    ...rest,
  };
}

const BUOI: BuoiTiepDon[] = [
  {
    ma: "SANG",
    nhan: "Sáng · 08:00 – 13:00",
    dong: [
      dong({ appointment_id: "1" }),
      dong({ appointment_id: "2", ten: "Hoàng Phương Chi", sdt: "0900 002 474", so_booking: 6, nhom: "da_den" }),
    ],
  },
  {
    ma: "CHIEU",
    nhan: "Chiều · 14:00 – 17:30",
    dong: [dong({ appointment_id: "3", ten: "Lê Mai", ma_khach: "BN-9", so_booking: 15, nhom: "khac" })],
  },
];

const ids = (b: BuoiTiepDon[]) => b.flatMap((x) => x.dong.map((d) => d.appointment_id));

test("tab lọc theo nhóm máy chủ trả; Tất cả gồm cả 'không đến'", () => {
  assert.deepEqual(ids(locTiepDon(BUOI, "tat_ca", "")), ["1", "2", "3"]);
  assert.deepEqual(ids(locTiepDon(BUOI, "chua_den", "")), ["1"]);
  assert.deepEqual(ids(locTiepDon(BUOI, "da_den", "")), ["2"]);
  // Buổi không còn dòng nào thì bỏ cả đầu nhóm.
  assert.deepEqual(locTiepDon(BUOI, "da_den", "").map((b) => b.ma), ["SANG"]);
});

test("ô tìm: tên không dấu, mã khách, #booking, SĐT theo chữ số", () => {
  assert.deepEqual(ids(locTiepDon(BUOI, "tat_ca", "phuong chi")), ["2"]);
  assert.deepEqual(ids(locTiepDon(BUOI, "tat_ca", "  BN-9 ")), ["3"]);
  assert.deepEqual(ids(locTiepDon(BUOI, "tat_ca", "#15")), ["3"]);
  assert.deepEqual(ids(locTiepDon(BUOI, "tat_ca", "002 474")), ["2"]);
  assert.deepEqual(ids(locTiepDon(BUOI, "tat_ca", "0900002474")), ["2"]);
  assert.deepEqual(ids(locTiepDon(BUOI, "tat_ca", "không ai")), []);
});

test("đầu vào rác không ném", () => {
  assert.deepEqual(locTiepDon(null, "tat_ca", "x"), []);
  assert.deepEqual(locTiepDon(undefined, "tat_ca", ""), []);
  // @ts-expect-error — dữ liệu hỏng từ mạng
  assert.deepEqual(locTiepDon([{ ma: "X", nhan: "", dong: null }], "tat_ca", ""), []);
  // @ts-expect-error — ô tìm không phải chuỗi
  assert.equal(ids(locTiepDon(BUOI, "tat_ca", null)).length, 3);
  const thieu = [{ ma: "S", nhan: "", dong: [dong({ ten: null, ma_khach: null, sdt: null, so_booking: null })] }];
  assert.deepEqual(ids(locTiepDon(thieu, "tat_ca", "12")), []);
});

test("tông màu theo loại, loại lạ về xám", () => {
  assert.equal(toneTrangThai("cho"), "neutral");
  assert.equal(toneTrangThai("tre"), "warning");
  assert.equal(toneTrangThai("den"), "success");
  assert.equal(toneTrangThai("dang_o"), "dang_o");
  assert.equal(toneTrangThai("ve"), "neutral");
  assert.equal(toneTrangThai("lạ"), "neutral");
});

test("chuanHoa và dòng phụ", () => {
  assert.equal(chuanHoa("  Đỗ  Thanh   GIANG "), "do thanh giang");
  assert.equal(dongPhu(["08:30", null, "", "  ", "BS A", "0900"]), "08:30 · BS A · 0900");
  assert.equal(dongPhu([]), "");
});
