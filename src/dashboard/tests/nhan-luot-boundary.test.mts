// NHÃN ĐẾM LƯỢT (Tuyền chốt 08/10/2026): mỗi lần check-in = MỘT lượt khám, đếm
// theo thời gian trên TOÀN BỘ lượt của khách ("Lượt khám n"); điều trị đếm theo
// buổi ("Buổi k/N" / "Điều trị · buổi lẻ"); lịch chưa tới "Lịch hẹn", huỷ "Đã
// huỷ". MÁY CHỦ đếm (`services/nhan_luot.py`) — TSX chỉ vẽ `nhan_luot`, không
// còn "Lần đầu" / "Tái khám n" / "Lần {i}" theo chỉ số mảng ở bất kỳ lối nào.
// Khung phải `/customers`: lượt đã tới hiện giờ THẬT (đến · khám xong · về),
// không giờ hẹn slot.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { chipBuoiPhu, chuNhanLuot, gioLuot, type NhanLuot } from "../lib/nhan-luot.ts";

const read = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");
/** Bỏ chú thích (// … và /* … *\/) — chú thích được kể chuyện cũ "Lần đầu". */
const boChuThich = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");

const LOI = {
  thanh: read("../app/(dashboard)/customers/ThanhLuotKham.tsx"),
  lichSuCacLan: read("../app/(dashboard)/customers/LichSuCacLanKham.tsx"),
  banKham: read("../app/(dashboard)/doctor/board/LuotKhamTruoc.tsx"),
  popup: read("../app/(dashboard)/_lam-viec/LichSuKham.tsx"),
  patientList: read("../app/(dashboard)/patient-list/PatientListView.tsx"),
  benhAn: read("../app/(dashboard)/tasks/ClinicalRecordForm.tsx"),
};
const PAGE = read("../app/(dashboard)/customers/page.tsx");
const VIEW = read("../app/(dashboard)/customers/CustomersView.tsx");

const kham = (n: number): NhanLuot => ({ nhan: `Lượt khám ${n}`, loai: "KHAM", so: n, buoi: null });

test("chữ nhãn: lấy đúng chữ máy chủ; thiếu → chữ trung tính, không tự đếm", () => {
  assert.equal(chuNhanLuot(kham(2)), "Lượt khám 2");
  assert.equal(chuNhanLuot({ nhan: "Buổi 3/10", loai: "DIEU_TRI", so: null, buoi: "Buổi 3/10" }), "Buổi 3/10");
  assert.equal(chuNhanLuot(null), "Lượt");
  assert.equal(chuNhanLuot(undefined, "Đã huỷ"), "Đã huỷ");
  // Chip phụ "Buổi k/N" chỉ cho lượt KHÁM có làm buổi liệu trình.
  assert.equal(chipBuoiPhu({ ...kham(1), buoi: "Buổi 1/10" }), "Buổi 1/10");
  assert.equal(chipBuoiPhu({ nhan: "Buổi 2/10", loai: "DIEU_TRI", so: null, buoi: "Buổi 2/10" }), null);
  assert.equal(chipBuoiPhu(null), null);
});

test("giờ lượt: đã tới → giờ thật (đến · khám xong · về), chưa tới → giờ hẹn", () => {
  // Ảnh Tuyền: slot 20:30, khách đến 08:12, khám xong 09:40, về 09:59.
  const s = gioLuot({
    slot_start: "2026-10-08T13:30:00Z",
    bat_dau: "2026-10-08T01:12:00Z",
    kham_xong_luc: "2026-10-08T02:40:00Z",
    ket_thuc: "2026-10-08T02:59:00Z",
  });
  assert.match(s, /đến 08:12/);
  assert.match(s, /khám xong 09:40/);
  assert.match(s, /về 09:59/);
  assert.doesNotMatch(s, /20:30/);
  // Đã tới, chưa khám xong / chưa về → bỏ mốc chưa có.
  const dang = gioLuot({ slot_start: "2026-10-08T13:30:00Z", bat_dau: "2026-10-08T01:12:00Z" });
  assert.doesNotMatch(dang, /khám xong|về/);
  // Chưa tới → giờ hẹn.
  assert.match(gioLuot({ slot_start: "2026-10-08T13:30:00Z" }), /20:30/);
  assert.equal(gioLuot({}), "Chưa có lịch hẹn");
  // Rác không ném.
  assert.doesNotThrow(() => gioLuot({ bat_dau: "rác", kham_xong_luc: "x", ket_thuc: "" }));
});

test("mọi lối hiện nhãn lượt dùng nhãn máy chủ, không tự đếm theo chỉ số", () => {
  for (const [ten, goc] of Object.entries(LOI)) {
    const s = boChuThich(goc);
    assert.match(s, /chuNhanLuot\(/, `${ten} phải vẽ nhan_luot`);
    assert.doesNotMatch(s, /Lần đầu|Tái khám \$\{|tái khám lần \{|Lần \{|`Lần \$\{/, `${ten} còn tự đếm`);
  }
});

test("/customers: một dải theo thời gian, không gom chuỗi theo lich_truoc_id", () => {
  assert.doesNotMatch(PAGE, /chuoiCuaLuot/);
  assert.match(PAGE, /nhan_luot: a\.nhan_luot \?\? null/);
  assert.doesNotMatch(LOI.lichSuCacLan, /đợt khám riêng/);
});

test("khung phải: không in giờ hẹn slot cho lượt đã tới", () => {
  assert.doesNotMatch(VIEW, /fmtDateTimeOrDate\(luotDangXem(\?)?\.slot_start/);
  assert.equal((VIEW.match(/gioLuot\(luotDangXem\)/g) ?? []).length, 2);
});
