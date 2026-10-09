import assert from "node:assert/strict";
import test from "node:test";

import {
  chuanHoa,
  dangLoc,
  docHuongXep,
  dongPhu,
  laHuongXep,
  locLichHen,
  locTiepDon,
  nhomLichHen,
  sapXepTiepDon,
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

test("sắp xếp: cũ trước giữ nguyên thứ tự máy chủ; mới trước đảo cả buổi lẫn dòng", () => {
  assert.deepEqual(ids(sapXepTiepDon(BUOI, "cu_truoc")), ["1", "2", "3"]);
  const moi = sapXepTiepDon(BUOI, "moi_truoc");
  assert.deepEqual(moi.map((b) => b.ma), ["CHIEU", "SANG"]);
  assert.deepEqual(ids(moi), ["3", "2", "1"]);
  // Không sửa mảng của máy chủ.
  assert.deepEqual(ids(BUOI), ["1", "2", "3"]);
  // Lọc sau khi đảo vẫn đúng.
  assert.deepEqual(ids(locTiepDon(moi, "chua_den", "")), ["1"]);
});

test("sắp xếp + nhớ lựa chọn: rác không ném, không có kho thì về mặc định", () => {
  assert.deepEqual(sapXepTiepDon(null, "moi_truoc"), []);
  // @ts-expect-error — dữ liệu hỏng từ mạng
  assert.deepEqual(sapXepTiepDon([{ ma: "X", nhan: "", dong: null }], "moi_truoc"), [
    { ma: "X", nhan: "", dong: [] },
  ]);
  assert.equal(laHuongXep("moi_truoc"), true);
  assert.equal(laHuongXep("lạ"), false);
  assert.equal(laHuongXep(null), false);
  assert.equal(docHuongXep(), "cu_truoc"); // node không có window
});

// ── Thanh lọc trên cùng màn Tiếp đón lọc CẢ bảng Lịch hẹn (09/10/2026) ──────────
const NGAY = [
  {
    date: "2026-10-09",
    items: [
      { id: "x1", status: "CONFIRMED", so_booking: 3, patient: { full_name: "Nguyễn Thị Ngà", patient_code: "BN-01", phone_primary: "0900 001 237" } },
      { id: "x2", status: "CHECKED_IN", so_booking: 12, patient: { full_name: "Trần Mai", patient_code: "BN-02", phone_primary: null } },
      { id: "x3", status: "COMPLETED", so_booking: 7, patient: { full_name: "Lê Hoa", patient_code: "BN-03", phone_primary: "0911222333" } },
      { id: "x4", status: "NO_SHOW", so_booking: 8, patient: null },
    ],
  },
  { date: "2026-10-10", items: [] },
];
const ma = (ds: { items: { id: string }[] }[]) => ds.flatMap((d) => d.items.map((a) => a.id));

test("lọc lịch hẹn: tab chưa đến / đã check-in cùng nghĩa với danh sách tiếp đón", () => {
  assert.equal(nhomLichHen("SCHEDULED"), "chua_den");
  assert.equal(nhomLichHen("CONFIRMED"), "chua_den");
  assert.equal(nhomLichHen("CHECKED_IN"), "da_den");
  assert.equal(nhomLichHen("COMPLETED"), "da_den");
  assert.equal(nhomLichHen("NO_SHOW"), "khac");
  assert.equal(nhomLichHen(undefined), "khac");
  assert.deepEqual(ma(locLichHen(NGAY, { tab: "chua_den", tim: "" })), ["x1"]);
  assert.deepEqual(ma(locLichHen(NGAY, { tab: "da_den", tim: "" })), ["x2", "x3"]);
  assert.deepEqual(ma(locLichHen(NGAY, { tab: "tat_ca", tim: "" })), ["x1", "x2", "x3", "x4"]);
  // Giữ mọi ngày — dải ngày không nhảy khi lọc.
  assert.equal(locLichHen(NGAY, { tab: "da_den", tim: "" }).length, 2);
});

test("lọc lịch hẹn: ô tìm theo tên không dấu, mã, #booking, SĐT theo chữ số", () => {
  assert.deepEqual(ma(locLichHen(NGAY, { tab: "tat_ca", tim: "nga" })), ["x1"]);
  assert.deepEqual(ma(locLichHen(NGAY, { tab: "tat_ca", tim: "bn-02" })), ["x2"]);
  assert.deepEqual(ma(locLichHen(NGAY, { tab: "tat_ca", tim: "#7" })), ["x3"]);
  assert.deepEqual(ma(locLichHen(NGAY, { tab: "tat_ca", tim: "0900001" })), ["x1"]);
  assert.deepEqual(ma(locLichHen(NGAY, { tab: "da_den", tim: "hoa" })), ["x3"]);
  assert.deepEqual(ma(locLichHen(NGAY, { tab: "chua_den", tim: "hoa" })), []);
});

test("lọc lịch hẹn: rác không ném, không lọc thì trả nguyên", () => {
  assert.equal(dangLoc(null), false);
  assert.equal(dangLoc({ tab: "tat_ca", tim: "  " }), false);
  assert.equal(dangLoc({ tab: "da_den", tim: "" }), true);
  assert.deepEqual(locLichHen(null, { tab: "da_den", tim: "" }), []);
  assert.deepEqual(ma(locLichHen(NGAY, null)), ["x1", "x2", "x3", "x4"]);
  // @ts-expect-error — tab lạ coi như "Tất cả"
  assert.deepEqual(ma(locLichHen(NGAY, { tab: "lạ", tim: "mai" })), ["x2"]);
  // @ts-expect-error — dữ liệu hỏng từ mạng
  assert.deepEqual(locLichHen([{ date: "d", items: null }], { tab: "da_den", tim: "" }), [
    { date: "d", items: [] },
  ]);
});
