// Bảng lịch hẹn (Tiếp đón / Trang chủ) — đích của từng nút, Tuyền bấm thật trên
// prod 29/09/2026.
//
// · Menu ⋯: "Gọi / ghi chăm sóc", "Huỷ lịch (ghi lý do)" từng chỉ là Link sang
//   `/customers?selected=…&luot=…` — rời màn, mở danh sách khách, không làm đúng
//   việc theo tên. Nay là popover TẠI CHỖ. "Mở hồ sơ khách" → Danh sách bệnh
//   nhân với khách chọn sẵn (`/patient-list?chon=`).
// · Dòng "＋ Thêm khách hàng" ở Tiếp đón từng trỏ nhầm sang màn Đặt lịch — phải
//   về màn Thêm khách hàng (`/patients/new?date&time&doctor`), như nút ở thanh
//   QueueBoard.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { hrefDatLich, hrefHoSoKhach, hrefThemKhach } from "../lib/lien-ket-lich.ts";

const doc = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");

const bang = doc("../app/(dashboard)/home/WeeklyAppointmentsTable.tsx");
const taiCho = doc("../app/(dashboard)/_lam-viec/ThaoTacLichTaiCho.tsx");
const trangChu = doc("../app/(dashboard)/home/page.tsx");
const tiepDon = doc("../app/(dashboard)/reception/queue/page.tsx");
const queueBoard = doc("../app/(dashboard)/reception/queue/QueueBoard.tsx");
const trangThemKhach = doc("../app/(dashboard)/patients/new/page.tsx");
const danhSachBn = doc("../app/(dashboard)/patient-list/page.tsx");

const menu = bang.slice(bang.indexOf("function MenuLich("), bang.indexOf("export default function"));

test("Thêm khách hàng: đúng màn + đúng tên tham số màn ấy đọc", () => {
  const u = new URL(hrefThemKhach({ ngay: "2026-09-30", gio: "09:15", bacSi: "bs-1" }), "http://x");
  assert.equal(u.pathname, "/patients/new");
  assert.equal(u.searchParams.get("date"), "2026-09-30");
  assert.equal(u.searchParams.get("time"), "09:15");
  assert.equal(u.searchParams.get("doctor"), "bs-1");
  assert.equal(hrefThemKhach(), "/patients/new");
  // Tên tham số khớp đúng thứ trang Thêm khách hàng đọc.
  assert.match(trangThemKhach, /const \{ date: qDate, time: qTime, doctor: qDoctor/);
});

test("dòng '＋ Thêm khách hàng' của quầy về màn Thêm khách hàng, không về Đặt lịch", () => {
  assert.doesNotMatch(bang, /`\/appointments\?ngay=/);
  assert.match(bang, /href: themKhach \? hrefThemKhach\(khung\) : hrefDatLich\(khung\)/);
  // Nhãn và đích đi theo CÙNG một cờ — không lệch nhau.
  assert.match(bang, /\{r\.free\.themKhach\s*\?\s*"＋ Thêm khách hàng"/);
  // Cờ theo LEGO Tiếp đón (mở full lego 30/09/2026); vai chỉ là đường lùi.
  assert.match(bang, /\s*duocCheckIn \?\? canCheckin\(role\),\n/);
  // CSKH/Quản lý vẫn "＋ Đặt lịch vào đây" → màn Đặt lịch.
  assert.equal(
    hrefDatLich({ ngay: "2026-09-30", gio: "09:15", bacSi: "bs-1" }),
    "/appointments?ngay=2026-09-30&gio=09%3A15&bac_si=bs-1",
  );
});

test("nút '+ Thêm khách hàng' ở thanh QueueBoard trỏ cùng màn", () => {
  assert.match(queueBoard, /<Link href=\{hrefThemKhach\(\)\}[^>]*>\s*\+ Thêm khách hàng/);
});

test("Mở hồ sơ khách → Danh sách bệnh nhân chọn sẵn khách, cùng tab", () => {
  assert.equal(hrefHoSoKhach("abc-1"), "/patient-list?chon=abc-1");
  assert.match(danhSachBn, /chonSan=\{typeof chon === "string" \? chon : null\}/);
  const i = menu.indexOf("Mở hồ sơ khách");
  assert.ok(i > 0);
  const truoc = menu.slice(Math.max(0, i - 120), i);
  assert.match(truoc, /<Link href=\{hrefHoSoKhach\(pid\)\} className=\{MUC\}>/);
  assert.doesNotMatch(truoc, /target=/);
  for (const trang of [trangChu, tiepDon]) {
    assert.match(trang, /duocXemHoSo=\{/);
  }
  assert.match(trangChu, /duocXemHoSo=\{vaoDuocMan\("\/patient-list"/);
  assert.match(tiepDon, /moDuocMan\("\/patient-list"\)/);
});

test("Gọi / Huỷ là nút mở popover tại chỗ, không link sang /customers", () => {
  assert.ok(menu.length > 0, "không tìm thấy MenuLich");
  assert.doesNotMatch(menu, /\/customers\?selected=/);
  for (const [nhan, loai] of [
    ["Gọi / ghi chăm sóc", "goi"],
    ["Huỷ lịch (ghi lý do)", "huy"],
  ]) {
    const i = menu.indexOf(nhan);
    assert.ok(i > 0, `thiếu mục "${nhan}"`);
    const truoc = menu.slice(Math.max(0, i - 200), i);
    assert.match(truoc, new RegExp(`<button type="button"[^>]*moTaiCho\\("${loai}"\\)`));
  }
  assert.match(menu, /duocGhiChamSoc \? \(/);
  // Huỷ theo booking.manage (duocDoiLich) + lịch còn sống.
  assert.match(menu, /const doiDuoc = duocDoiLich && CON_SONG\.includes\(a\.status\)/);
  for (const trang of [trangChu, tiepDon]) {
    assert.match(trang, /duocGhiChamSoc=\{coMotQuyen\(quyen, QUYEN_GHI_CHAM_SOC\)\}/);
  }
});

test("huỷ đi đúng đường máy chủ, gửi MÃ lý do từ danh mục chung", () => {
  assert.match(taiCho, /fetch\("\/api\/appointments", \{\s*method: "PATCH"/);
  assert.match(taiCho, /action: "cancel"/);
  assert.match(taiCho, /ly_do_huy_ma: ma/);
  assert.match(taiCho, /from "@\/lib\/ly-do-huy"/);
  // Không tự chép một danh mục lý do thứ năm.
  assert.doesNotMatch(taiCho, /BAO_KHI_XAC_NHAN/);
  assert.match(taiCho, /variant="danger"/);
});

test("ghi chăm sóc dùng lại sổ tương tác + khoá chống ghi trùng", () => {
  assert.match(taiCho, /fetch\("\/api\/cskh\/tuong-tac"/);
  assert.match(taiCho, /"Idempotency-Key": khoaThaoTac\(/);
  assert.match(taiCho, /href=\{`tel:\$\{lich\.sdt\}`\}/);
});

test("luật giao diện: không window.confirm, không style={{}}, <button> có type", () => {
  for (const src of [taiCho, menu]) {
    assert.doesNotMatch(src, /window\.confirm/);
    assert.doesNotMatch(src, /style=\{\{/);
    assert.doesNotMatch(src, /#[0-9a-fA-F]{6}\b/);
    for (const m of src.matchAll(/<button\b[^>]*>/g)) {
      assert.match(m[0], /type=/, `thiếu type: ${m[0]}`);
    }
  }
});
