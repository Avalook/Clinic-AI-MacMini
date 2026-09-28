// Đợt 3 (27/09/2026) — ba góp ý của phòng khám:
//   A1 "Thoát" lên góc phải đầu trang (thẻ tên bấm được);
//   A2 Trang chủ: lịch hẹn xem theo NGÀY (chip T2…CN + "Cả tuần", `?ngay=`);
//   A8 Check-out ở ngay chỗ đang nhìn khách (Tiếp đón · Hành trình · Thu ngân).

import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";

import {
  CA_TUAN,
  tabNgay,
  locTheoNgay,
  ngayDangChon,
} from "../app/(dashboard)/home/loc-ngay.ts";
import { checkOutDuoc, coQuyen, QUYEN_CHECK_OUT } from "../lib/quyen-client.ts";
import { weekDates } from "../lib/roster.ts";

const doc = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");
/** Mã thực thi — bỏ chú thích để chữ trong chú thích không làm bài kiểm nhầm. */
const ma = (p: string) =>
  doc(p)
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/.*$/gm, "$1");

// Tuần 21/09 (T2) → 27/09/2026 (CN).
const TUAN = weekDates("2026-09-21");

// ── A2: hàm thuần chọn ngày ────────────────────────────────────────────────

test("tuần này: không có ?ngay → mặc định HÔM NAY (kể cả hôm nay là CN)", () => {
  assert.equal(TUAN[6], "2026-09-27");
  assert.equal(ngayDangChon(null, TUAN, "2026-09-27"), "2026-09-27");
  assert.equal(ngayDangChon(undefined, TUAN, "2026-09-23"), "2026-09-23");
});

test("chọn một ngày trong tuần (cả CN) → đúng ngày ấy; 'ca-tuan' → cả tuần", () => {
  assert.equal(ngayDangChon("2026-09-21", TUAN, "2026-09-27"), "2026-09-21");
  assert.equal(ngayDangChon("2026-09-27", TUAN, "2026-09-23"), "2026-09-27");
  assert.equal(ngayDangChon(" 2026-09-22 ", TUAN, "2026-09-27"), "2026-09-22");
  assert.equal(ngayDangChon(CA_TUAN, TUAN, "2026-09-27"), null);
});

test("?ngay rác → bỏ qua, rơi về mặc định, KHÔNG ném", () => {
  for (const rac of ["abc", "", "2026-9-22", "2026-02-30", "2026-13-01", "22/09/2026", "null", "💥"]) {
    assert.doesNotThrow(() => ngayDangChon(rac, TUAN, "2026-09-27"));
    assert.equal(ngayDangChon(rac, TUAN, "2026-09-27"), "2026-09-27", `"${rac}"`);
  }
  // Kiểu lạ lọt vào (searchParams không bao giờ đưa, nhưng hàm không được nổ).
  assert.equal(ngayDangChon(42 as unknown as string, TUAN, "2026-09-27"), "2026-09-27");
});

test("tuần khác: ?ngay của tuần khác bị bỏ qua; mặc định là CẢ TUẦN", () => {
  const tuanSau = weekDates("2026-09-28");
  // Hôm nay (27/09) không nằm trong tuần sau → mặc định cả tuần.
  assert.equal(ngayDangChon(null, tuanSau, "2026-09-27"), null);
  assert.equal(ngayDangChon("abc", tuanSau, "2026-09-27"), null);
  // Ngày của tuần NÀY khi đang xem tuần sau → bỏ qua.
  assert.equal(ngayDangChon("2026-09-22", tuanSau, "2026-09-27"), null);
  // Ngày trong tuần sau → nhận.
  assert.equal(ngayDangChon("2026-10-01", tuanSau, "2026-09-27"), "2026-10-01");
  // Đang xem tuần này mà ?ngay trỏ tuần sau → về hôm nay.
  assert.equal(ngayDangChon("2026-10-01", TUAN, "2026-09-27"), "2026-09-27");
});

test("lọc ngày: null giữ cả tuần; một ngày thì còn đúng ngày ấy", () => {
  const days = TUAN.map((date, i) => ({ date, items: Array.from({ length: i }) }));
  assert.equal(locTheoNgay(days, null).length, 7);
  assert.deepEqual(
    locTheoNgay(days, "2026-09-27").map((d) => d.date),
    ["2026-09-27"],
  );
  assert.deepEqual(locTheoNgay(days, "2026-10-01"), []);
});

test("tab ngày: 'Cả tuần' đứng đầu, rồi T2…CN kèm ngày; số lịch để riêng", () => {
  const days = TUAN.map((date, i) => ({ date, items: i === 6 ? [1, 2, 3] : [] }));
  const tab = tabNgay(days);
  assert.equal(tab.length, 8);
  assert.deepEqual(tab[0], { ma: CA_TUAN, nhan: "Cả tuần", so: 0 });
  assert.equal(tab[1].nhan, "T2 21");
  assert.equal(tab[7].nhan, "CN 27");
  assert.equal(tab[7].so, 3);
  assert.equal(tab[7].ma, "2026-09-27");
});

test("chip ngày CHỈ bật ở Trang chủ; Tiếp đón dùng cùng bảng mà không truyền", () => {
  assert.match(ma("../app/(dashboard)/home/page.tsx"), /<WeeklyAppointmentsTable[\s\S]*?chonNgay[\s\S]*?\/>/);
  assert.doesNotMatch(ma("../app/(dashboard)/reception/queue/page.tsx"), /chonNgay/);
  const bang = ma("../app/(dashboard)/home/WeeklyAppointmentsTable.tsx");
  assert.match(bang, /chonNgay = false/);
  // Đọc từ URL mỗi lần vẽ, ghi lại URL không tải trang.
  assert.match(bang, /searchParams\.get\("ngay"\)/);
  assert.match(bang, /window\.history\.replaceState/);
  // Dải tab (27/09/2026) thay hàng chip hộp.
  assert.match(bang, /role="tablist"/);
  assert.match(bang, /tabNgay\(days\)/);
});

// ── A1: Thoát ở thẻ tên đầu trang ──────────────────────────────────────────

test("thẻ tên là nút mở ô có form Thoát; thanh bên vẫn giữ lối phụ", () => {
  const h = ma("../app/(dashboard)/GlobalHeader.tsx");
  assert.match(h, /aria-expanded=\{theTenOpen\}/);
  assert.match(h, /<form action=\{leaveAction\}/);
  assert.match(h, /<Button type="submit"[^>]*>[\s\S]*?Thoát/);
  // Esc đóng + trả tiêu điểm; Tab ra ngoài đóng; bấm ngoài đóng.
  assert.match(h, /e\.key === "Escape"/);
  assert.match(h, /nutTenRef\.current\?\.focus\(\)/);
  assert.match(h, /onBlur=\{roiTheTen\}/);
  assert.match(h, /theTenRef\.current && !theTenRef\.current\.contains\(t\)/);
  // Thẻ tên không bị giấu ở màn hẹp: chỉ phần CHỮ ẩn dưới lg, nút thì luôn có.
  assert.doesNotMatch(h, /ref=\{theTenRef\}\s+className="[^"]*hidden/);

  const shell = ma("../app/(dashboard)/Shell.tsx");
  assert.match(shell, /leaveAction=\{leaveAction\}/);
  assert.match(shell, /<form action=\{leaveAction\}>/);
});

test("LogoutButton.tsx (code chết, gọi signOut ở trình duyệt) đã xoá", () => {
  assert.equal(
    existsSync(new URL("../app/(dashboard)/LogoutButton.tsx", import.meta.url)),
    false,
  );
});

// ── A8: Check-out ở mọi chỗ đang nhìn khách ────────────────────────────────

test("quyền check-out: theo capability, không theo vai; null → ẩn", () => {
  assert.equal(QUYEN_CHECK_OUT, "reception.checkin.perform");
  assert.equal(checkOutDuoc(null), false);
  assert.equal(checkOutDuoc(undefined), false);
  assert.equal(checkOutDuoc([]), false);
  assert.equal(checkOutDuoc(["payment.service.collect"]), false);
  assert.equal(checkOutDuoc(["payment.service.collect", "reception.checkin.perform"]), true);
  assert.equal(coQuyen("reception.checkin.perform" as unknown as string[], QUYEN_CHECK_OUT), false);
});

test("NutCheckOut: cùng lệnh với màn Check-out, xác nhận tại chỗ, không if vai", () => {
  const nut = ma("../app/(dashboard)/_lam-viec/NutCheckOut.tsx");
  assert.match(nut, /fetch\(\s*`\/api\/reception\/checkout\?visit_id=/);
  assert.match(nut, /fetch\("\/api\/reception\/checkout", \{\s*method: "POST"/);
  assert.match(nut, /<XacNhanTaiCho/);
  assert.match(nut, /useCheckOutDuoc\(\)/);
  assert.doesNotMatch(nut, /window\.confirm/);
  assert.doesNotMatch(nut, /role\s*===|ClinicRole|RECEPTION/);
  // Check-out ≠ khám dở: nút này không gửi "khách về giữa chừng".
  assert.match(nut, /incomplete: false/);
});

test("nút Check-out có mặt ở Tiếp đón (tab Đã check-in), Hành trình, quầy thu", () => {
  const queue = ma("../app/(dashboard)/reception/queue/QueueBoard.tsx");
  assert.match(queue, /d\.check_out_duoc && d\.visit_id \? \(\s*<NutCheckOut/);
  assert.match(ma("../app/(dashboard)/hanh-trinh/BangHanhTrinh.tsx"), /!l\.da_ve \? \(\s*<NutCheckOut/);
  const quay = ma("../app/(dashboard)/thu-ngan/QuayThuNgan.tsx");
  assert.match(quay, /\{vuaThu && vuaThu\.cau === xong \? \(\s*<NutCheckOut/);
  // Quyền đi qua context mà Shell phát — không màn nào tự đoán theo vai.
  assert.match(ma("../app/(dashboard)/Shell.tsx"), /<QuyenProvider value=\{quyen\}>/);
});
