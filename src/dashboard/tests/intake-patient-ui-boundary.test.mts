import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const home = readFileSync(
  new URL("../app/(dashboard)/home/page.tsx", import.meta.url),
  "utf8",
);
const patients = readFileSync(
  new URL("../app/(dashboard)/patient-list/PatientListView.tsx", import.meta.url),
  "utf8",
);
const intake = readFileSync(
  new URL("../app/(dashboard)/patients/new/NewPatientForm.tsx", import.meta.url),
  "utf8",
);
const formUi = readFileSync(
  new URL("../app/(dashboard)/form-ui.ts", import.meta.url),
  "utf8",
);
const visitProgress = readFileSync(
  new URL("../app/(dashboard)/home/VisitProgress.tsx", import.meta.url),
  "utf8",
);
const visitStatus = readFileSync(
  new URL("../app/(dashboard)/home/VisitStatusBoard.tsx", import.meta.url),
  "utf8",
);
const weeklyAppointments = readFileSync(
  new URL("../app/(dashboard)/home/WeeklyAppointmentsTable.tsx", import.meta.url),
  "utf8",
);
const workRoster = readFileSync(
  new URL("../app/(dashboard)/home/WorkRosterTable.tsx", import.meta.url),
  "utf8",
);
// Màu nền theo PHÒNG nằm ở khung dùng chung của ba bảng lịch làm việc.
const rosterGrid = readFileSync(
  new URL("../app/(dashboard)/RosterGrid.tsx", import.meta.url),
  "utf8",
);
const cinemaSlots = readFileSync(
  new URL("../app/(dashboard)/patients/CinemaSlotPicker.tsx", import.meta.url),
  "utf8",
);
const booking = readFileSync(
  new URL("../app/(dashboard)/patients/AppointmentBooking.tsx", import.meta.url),
  "utf8",
);
const doctorLoad = readFileSync(
  new URL("../app/(dashboard)/patients/DoctorLoadBoard.tsx", import.meta.url),
  "utf8",
);

test("the reception overview exposes a clearly bounded working surface", () => {
  assert.match(home, /aria-label=\{isReception \? "Tổng quan tiếp nhận"/);
  assert.match(home, /aria-label="Lịch hẹn khám"/);
  assert.match(home, /aria-label="Lịch làm việc"/);
  assert.match(home, /visitStatusRows/);
});

test("the patient directory follows the three-region reference layout without stale selection", () => {
  for (const label of [
    "Danh sách bệnh nhân",
    "Tổng quan hồ sơ",
    "Lượt khám gần nhất",
  ]) {
    assert.match(patients, new RegExp(`aria-label="${label}"`));
  }
  // 06/10/2026 (phân trang ở máy chủ): khách đang chọn lấy từ TRANG đang hiện,
  // hoặc từ `chonRow` máy chủ trả kèm — không giữ một dòng cũ đã bị lọc ra.
  assert.match(patients, /rows\.find\(\(item\) => item\.clinic_patient_id === selectedId\) \?\?/);
  assert.match(patients, /chonRow\?\.clinic_patient_id === selectedId \? chonRow : null/);

  // Phiếu khám vẫn mở được — nhưng CHỈ cho vai lâm sàng. Với Lễ tân nút đó chỉ
  // là liên kết sang trang hành chính, tức là bấm để đọc đúng khối hành chính
  // vừa hiện đầy đủ ngay bên cạnh.
  assert.match(patients, /Mở phiếu khám/);
  // Chốt là ENABLEPOPUP PHẢI ĐỨNG ĐẦU điều kiện, không phải cả câu điều kiện
  // phải y nguyên. Màn này đã thêm vế "&& selected.appt" (hồ sơ chưa khám lần
  // nào thì không có phiếu để mở) — siết theo chuỗi nguyên văn sẽ bắt lỗi một
  // thay đổi vô hại, và lần sau người ta sẽ sửa test cho qua thay vì đọc nó.
  assert.match(patients, /\{enablePopup(?: &&[^?]*)? \? \(/);

  // Khối hành chính hiện TẠI CHỖ, không bắt đổi màn để đọc thứ đã tải về.
  assert.match(patients, /HangHanhChinh/);
  assert.match(patients, /nhan="Ngày sinh"/);
  assert.match(patients, /nhan="Địa chỉ"/);

  // Xem được TỪNG lượt khám cũ, không chỉ đếm số lượng.
  assert.match(patients, /Các lượt khám \(/);
  assert.match(patients, /selected\.visits\.map/);

  assert.doesNotMatch(patients, /#ec4899|text-status-cancelled/);
});

test("intake makes the real patient-and-appointment flow legible", () => {
  assert.match(intake, /aria-label="Luồng tạo hồ sơ và đặt lịch"/);
  assert.match(intake, /Thông tin hồ sơ/);
  assert.match(intake, /Lịch hẹn khám/);
  assert.match(intake, /CinemaSlotPicker/);
  assert.match(intake, /\/api\/patients/);
  assert.match(intake, /\/api\/appointments/);
});

test("CSKH intake without an appointment returns to the selected customer before reception routing", () => {
  const customerRoute = intake.indexOf('if (role === "CSKH" && !walkin && !wantsAppointment)');
  const receptionRoute = intake.indexOf("if (veTiepDon)", customerRoute);
  assert.ok(customerRoute >= 0 && receptionRoute > customerRoute);
  assert.match(intake.slice(customerRoute, receptionRoute), /\/customers\?selected=\$\{encodeURIComponent\(id\)\}/);
});

test("saved customer routing preserves reception and walk-in destinations", () => {
  const routeBody = intake.match(/function goToProfile\(id: string, code\?: string, moi = false\) \{([\s\S]*?)\n  \}/)?.[1];
  assert.ok(routeBody);
  const makeRoute = new Function("role", "walkin", "wantsAppointment", "veTiepDon", "veQuanLyKhach", "router", "khoaNhapKhach", `return function(id, code, moi) {${routeBody}}`);
  for (const scenario of [
    { role: "CSKH", walkin: false, appointment: false, reception: true, destination: "/customers?selected=khach%201" },
    { role: "CSKH", walkin: false, appointment: false, reception: false, destination: "/customers?selected=khach%201" },
    { role: "CSKH", walkin: false, appointment: true, reception: true, destination: "/reception/queue" },
    { role: "RECEPTION", walkin: false, appointment: false, reception: true, destination: "/reception/queue" },
    { role: "RECEPTION", walkin: false, appointment: false, reception: false, destination: "/patient-list" },
    { role: "NURSE", walkin: true, appointment: false, reception: false, destination: "/patients/khach 1?new=1" },
  ]) {
    const destinations: string[] = [];
    const route = makeRoute(scenario.role, scenario.walkin, scenario.appointment, scenario.reception, false, { push: (url: string) => destinations.push(url) }, null);
    route("khach 1");
    assert.deepEqual(destinations, [scenario.destination]);
  }
});

test("quick intake Enter is limited to identity inputs and protects against duplicate saves", () => {
  assert.equal((intake.match(/onKeyDown=\{luuNhapNhanh\}/g) ?? []).length, 3);
  assert.match(intake, /e\.nativeEvent\.isComposing \|\| walkin \|\| wantsAppointment \|\| dupes/);
  assert.match(intake, /if \(submitting \|\| submittingRef\.current\) return;/);
  assert.match(intake, /submittingRef\.current = true;/);
  assert.match(intake, /finally \{\s*submittingRef\.current = false;/);
  assert.match(intake, /Không lưu được hồ sơ/);
});

test("quick intake Enter saves once while composition and appointment controls keep their normal behavior", () => {
  const handler = intake.match(/function luuNhapNhanh\(e: KeyboardEvent<HTMLInputElement>\) \{([\s\S]*?)\n  \}/)?.[1];
  assert.ok(handler, "Quick intake handler is present");
  const makeHandler = new Function("walkin", "wantsAppointment", "dupes", "save", `return function(e) {${handler}}`);
  for (const scenario of [
    { key: "Enter", composing: false, walkin: false, appointment: false, dupes: null, saved: 1 },
    { key: "Tab", composing: false, walkin: false, appointment: false, dupes: null, saved: 0 },
    { key: "Enter", composing: true, walkin: false, appointment: false, dupes: null, saved: 0 },
    { key: "Enter", composing: false, walkin: true, appointment: false, dupes: null, saved: 0 },
    { key: "Enter", composing: false, walkin: false, appointment: true, dupes: null, saved: 0 },
    { key: "Enter", composing: false, walkin: false, appointment: false, dupes: [], saved: 0 },
  ]) {
    let saves = 0;
    let prevented = 0;
    const run = makeHandler(scenario.walkin, scenario.appointment, scenario.dupes, (force: boolean) => {
      assert.equal(force, false);
      saves += 1;
    });
    run({ key: scenario.key, nativeEvent: { isComposing: scenario.composing }, preventDefault: () => { prevented += 1; } });
    assert.equal(saves, scenario.saved, JSON.stringify(scenario));
    assert.equal(prevented, scenario.saved, JSON.stringify(scenario));
  }
});

// "Số thứ tự gọi khám" (/queue, ẩn từ 03/07) gộp vào Tiếp đón khách
// 18/09/2026 — bài kiểm "trang chỉ còn chuyển hướng" ở man-da-gop-boundary.

test("reception and patient surfaces use the shared color and shadow tokens", () => {
  const sources = [
    formUi,
    visitProgress,
    visitStatus,
    weeklyAppointments,
    workRoster,
    cinemaSlots,
    booking,
    doctorLoad,
    intake,
    rosterGrid,
  ].join("\n");

  assert.doesNotMatch(sources, /#[0-9a-f]{3,8}\b/i);
  assert.doesNotMatch(sources, /\b(?:pink|rose|fuchsia)\b/i);
  assert.doesNotMatch(sources, /rgba\(/i);
  assert.match(formUi, /shadow-card/);
  assert.match(booking, /ui\.className/);
  // Bảng lịch lấy màu qua `mauPhong` (bảng MAU_PHONG khoá theo MÃ phòng, 27/09
  // đợt 3) — token `--color-lich-*` mang đúng mã màu file Excel (16/09/2026).
  // Thứ canh vẫn là một: màu đi qua bảng token dùng chung, không có mã hex
  // nằm trong TSX.
  assert.match(rosterGrid, /mauPhong\(/);
});
