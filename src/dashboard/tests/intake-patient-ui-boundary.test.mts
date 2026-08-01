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
const profile = readFileSync(
  new URL("../app/(dashboard)/patients/[id]/PatientDetail.tsx", import.meta.url),
  "utf8",
);
const queuePage = readFileSync(
  new URL("../app/(dashboard)/queue/page.tsx", import.meta.url),
  "utf8",
);
const queue = readFileSync(
  new URL("../app/(dashboard)/queue/QueueBoard.tsx", import.meta.url),
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
const homeCheckin = readFileSync(
  new URL("../app/(dashboard)/home/HomeCheckin.tsx", import.meta.url),
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
const cskhLog = readFileSync(
  new URL("../app/(dashboard)/patients/[id]/PatientCskhLog.tsx", import.meta.url),
  "utf8",
);
const patientHistory = readFileSync(
  new URL("../app/(dashboard)/patients/[id]/PatientHistory.tsx", import.meta.url),
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
  assert.match(patients, /shown\.find\(\(item\) => item\.clinic_patient_id === selectedId\) \?\?/);
  assert.match(patients, /Mở hồ sơ khám/);
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

test("the patient profile keeps administrative and appointment data distinct", () => {
  assert.match(profile, /aria-label="Thông tin hành chính bệnh nhân"/);
  assert.match(profile, /aria-label="Lịch sử lịch hẹn"/);
  assert.doesNotMatch(profile.replace(/\/\/.*$/gm, ""), /national_id_number/);
});

test("the internal queue remains gated and does not pretend to be a public calling display", () => {
  assert.match(queuePage, /requireNavAccess\("\/queue"\)/);
  assert.match(queue, /aria-label="Bảng điều phối hàng đợi nội bộ"/);
  assert.match(queue, /router\.refresh\(\)/);
  assert.doesNotMatch(queue, /Gọi số|ĐANG GỌI/);
});

test("reception and patient surfaces use the shared color and shadow tokens", () => {
  const sources = [
    formUi,
    visitProgress,
    visitStatus,
    homeCheckin,
    weeklyAppointments,
    workRoster,
    cinemaSlots,
    booking,
    doctorLoad,
    intake,
    cskhLog,
    patientHistory,
  ].join("\n");

  assert.doesNotMatch(sources, /#[0-9a-f]{3,8}\b/i);
  assert.doesNotMatch(sources, /\b(?:pink|rose|fuchsia)\b/i);
  assert.doesNotMatch(sources, /rgba\(/i);
  assert.match(formUi, /shadow-card/);
  assert.match(booking, /ui\.className/);
  assert.match(workRoster, /floorBorderClass/);
});
