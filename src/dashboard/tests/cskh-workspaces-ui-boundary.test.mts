import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path: string) =>
  readFileSync(new URL(path, import.meta.url), "utf8");

const todayPage = read("../app/(dashboard)/cskh-today/page.tsx");
const todayWorkspace = read(
  "../app/(dashboard)/cskh-today/CskhTodayWorkspace.tsx",
);
const followups = read("../app/(dashboard)/cskh-today/CskhFollowupList.tsx");
const customersPage = read("../app/(dashboard)/customers/page.tsx");
const customers = read("../app/(dashboard)/customers/CustomersView.tsx");
const appointmentsPage = read("../app/(dashboard)/appointments/page.tsx");
const appointments = read(
  "../app/(dashboard)/appointments/AppointmentsWorkspace.tsx",
);
const kanban = read("../app/(dashboard)/appointments/AppointmentsKanban.tsx");
const realtime = read("../app/(dashboard)/appointments/AppointmentsRealtime.tsx");
const appointmentEdit = read("../app/(dashboard)/customers/AppointmentEditModal.tsx");
const statCard = read("../components/ui/StatCard.tsx");
const episodesPage = read("../app/(dashboard)/episodes/page.tsx");
const episodes = read("../app/(dashboard)/episodes/EpisodesBoard.tsx");

test("CSKH follow-up workspace keeps list, detail and coordination regions", () => {
  for (const label of [
    "Danh sách việc CSKH",
    "Chi tiết công việc",
    "Điều phối công việc",
    "Tất cả việc",
    "Lịch ngày mai",
    "Kết quả XN",
  ]) {
    assert.match(todayWorkspace, new RegExp(label));
  }
  assert.match(
    todayWorkspace,
    /xl:grid-cols-\[minmax\(250px,0\.9fr\)_minmax\(360px,1\.25fr\)_minmax\(240px,0\.8fr\)\]/,
  );
  assert.match(todayPage, /<CskhTodayWorkspace/);
  assert.match(followups, /fetch\("\/api\/cskh-followup"/);
  assert.match(todayWorkspace, /<FollowupMarkButton/);
  assert.match(todayWorkspace, /href=\{`\/customers\?selected=\$\{selected\.patientId\}`\}/);
});

test("CSKH customer directory uses the catalogue-style table and a real detail panel", () => {
  for (const label of [
    "Danh sách khách hàng",
    "Chi tiết khách hàng",
    "Tất cả khách hàng",
    "Có lịch sắp tới",
    "Chưa có lịch",
    "Khách hiển thị",
  ]) {
    assert.match(customers, new RegExp(label));
  }
  assert.match(
    customers,
    /xl:grid-cols-\[minmax\(0,1fr\)_minmax\(300px,380px\)\]/,
  );
  assert.match(customers, /<AppointmentEditModal/);
  assert.match(customers, /<QuickBookingModal/);
  assert.match(customersPage, /requireNavAccess\("\/customers"\)/);
});

test("appointment workspace presents real booking facts but does not manufacture capacity", () => {
  for (const label of [
    "Danh sách lịch hẹn",
    "Lịch hẹn theo trạng thái",
    "Thông tin lịch hẹn",
    "Tìm tên, mã BN hoặc số thứ tự",
    "Chưa có dữ liệu sức chứa và giữ chỗ từ backend.",
  ]) {
    assert.match(appointments, new RegExp(label));
  }
  assert.match(
    appointments,
    /xl:grid-cols-\[minmax\(230px,0\.82fr\)_minmax\(440px,1\.55fr\)_minmax\(250px,0\.9fr\)\]/,
  );
  assert.match(appointmentsPage, /<AppointmentsWorkspace/);
  assert.match(appointments, /<AppointmentActions/);
  assert.doesNotMatch(appointments, /0\/3|1\/3|2\/3|3\/3/);
  assert.doesNotMatch(kanban, /#[0-9a-f]{3,8}/iu);
});

test("episode confirmation retains its actual close and reopen contract in a three-region workspace", () => {
  for (const label of [
    "Danh sách đợt chờ xác nhận",
    "Chi tiết đợt khám",
    "Quyết định CSKH",
    "Tìm bệnh nhân hoặc mã hồ sơ",
    "Xác nhận đóng",
    "Còn theo dõi",
  ]) {
    assert.match(episodes, new RegExp(label));
  }
  assert.match(
    episodes,
    /xl:grid-cols-\[minmax\(240px,0\.82fr\)_minmax\(360px,1\.25fr\)_minmax\(250px,0\.86fr\)\]/,
  );
  assert.match(episodes, /fetch\("\/api\/episodes"/);
  assert.match(episodesPage, /requireNavAccess\("\/episodes"\)/);
});

test("CSKH redesign uses the shared ClinicAI tokens instead of an extra palette", () => {
  for (const source of [
    todayPage,
    todayWorkspace,
    followups,
    customersPage,
    customers,
    appointmentsPage,
    appointments,
    kanban,
    realtime,
    appointmentEdit,
    episodesPage,
    episodes,
  ]) {
    assert.doesNotMatch(source, /#[0-9a-f]{3,8}/iu);
    assert.doesNotMatch(source, /pink|rose|fuchsia/iu);
  }
  assert.match(statCard, /bg-warning-bg/);
  assert.match(statCard, /text-warning/);
  assert.doesNotMatch(statCard, /status-on-hold/);
});
