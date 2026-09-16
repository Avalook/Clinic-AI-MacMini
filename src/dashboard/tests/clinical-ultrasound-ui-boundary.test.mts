import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  cashierAmountState,
  canFinishService,
  paidCashierPaymentSeeds,
  resolveSaWorkflowStatus,
  sonoPatientDisplayName,
} from "../lib/clinical-workspace-policy.ts";

const read = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");

const doctor = read("../app/(dashboard)/tasks/DoctorWorkBoard.tsx");
const cashier = read("../app/(dashboard)/tasks/CashierWorkBoard.tsx");
const cskhActions = read("../app/(dashboard)/tasks/CskhActionBoard.tsx");
const clinicalForm = read("../app/(dashboard)/tasks/ClinicalRecordForm.tsx");
const confirmation = read("../app/(dashboard)/tasks/ConfirmBoard.tsx");
const serviceForm = read("../app/(dashboard)/tasks/ServiceFormEngine.tsx");
const biometry = read("../app/(dashboard)/tasks/SonoBiometry.tsx");
const tasksRealtime = read("../app/(dashboard)/tasks/TasksRealtime.tsx");
// Ba màn Lấy mẫu / Thủ thuật / Điều dưỡng siêu âm đã gộp thành MỘT màn phòng
// dịch vụ đọc hàng chờ theo chỉ định (Tuyền chốt 16/09/2026).
const phong = read("../app/(dashboard)/phong/[ma]/PhongDichVu.tsx");
const banKham = read("../app/(dashboard)/ban-kham/BanKham.tsx");
const khungTep = read("../app/(dashboard)/_lam-viec/KhungTep.tsx");
const hangCho = read("../app/(dashboard)/_lam-viec/HangChoCot.tsx");
const lamViecApi = read("../app/(dashboard)/_lam-viec/api.ts");
const cashierPage = read("../app/(dashboard)/tasks/page.tsx");
const statCard = read("../app/(dashboard)/StatCard.tsx");
const workspaceCss = read("../app/(dashboard)/tasks/WorkspacePrimitives.module.css");

test("clinical workspaces expose their reference-style working regions", () => {
  for (const [source, regions] of [
    [doctor, ["Hàng đợi khám bệnh", "Lịch khám và hồ sơ", "Điều phối lượt khám"]],
    [cashier, ["Danh sách khoản thu", "Chi tiết khoản thu", "Trạng thái thanh toán"]],
    [phong, ["Hàng chờ phòng"]],
    [banKham, ["Hàng chờ khám", "Hồ sơ khám bệnh", "Chỉ định và kết quả"]],
  ] as const) {
    for (const label of regions) {
      assert.match(source, new RegExp(`aria-label="${label}"`));
    }
  }
});

test("the refreshed clinical and ultrasound screens use only shared visual tokens", () => {
  for (const source of [
    doctor,
    cashier,
    cskhActions,
    clinicalForm,
    confirmation,
    serviceForm,
    biometry,
    tasksRealtime,
    cashierPage,
    statCard,
    phong,
    banKham,
    khungTep,
    hangCho,
  ]) {
    assert.doesNotMatch(source, /#[0-9a-f]{3,8}/iu);
    assert.doesNotMatch(source, /pink|rose|fuchsia/iu);
    assert.doesNotMatch(source, /rgba\(/iu);
    assert.doesNotMatch(source, /bg-white|bg-(?:red|orange|yellow|blue|green|gray)-/iu);
  }
});

test("redesigning does not replace the established mutation contracts", () => {
  assert.match(doctor, /<ClinicalRecordForm/);
  assert.match(cashier, /fetch\("\/api\/payment"/);
  // Màn phòng và bàn khám ghi qua ĐÚNG MỘT đường: /api/luot-kham.
  assert.match(lamViecApi, /fetch\("\/api\/luot-kham"/);
  for (const src of [phong, banKham]) {
    assert.doesNotMatch(src, /\/api\/(sono|service-log|lab-result|work-items)/);
  }
});

test("phòng dịch vụ: Bắt đầu → ghi kết quả + tệp → Xong / Không làm được", () => {
  assert.match(phong, /guiThaoTac|bam\("bat-dau-dich-vu"\)/);
  assert.match(phong, /"bat-dau-dich-vu"/);
  assert.match(phong, /"xong-dich-vu", \{ performed: true/);
  assert.match(phong, /performed: false,\s*reason: lyDo/);
  assert.match(phong, /<KhungTep/);
});

test("financial, patient, and ultrasound status fallbacks remain fail-safe", () => {
  assert.deepEqual(
    paidCashierPaymentSeeds([
      { visit_id: "visit-paid", kind: "thuoc", status: "PAID" },
      { visit_id: "visit-voided", kind: "thuoc", status: "VOIDED" },
      { visit_id: "visit-unknown", kind: "dich_vu", status: null },
      { visit_id: "visit-other", kind: "other", status: "PAID" },
    ]),
    [{ visit_id: "visit-paid", kind: "thuoc" }],
  );
  assert.equal(sonoPatientDisplayName(null), "Chưa gắn người bệnh");
  assert.equal(sonoPatientDisplayName("  Nguyễn An  "), "Nguyễn An");
  assert.equal(resolveSaWorkflowStatus("WAITING"), "WAITING");
  assert.equal(resolveSaWorkflowStatus(null), null);
  assert.equal(resolveSaWorkflowStatus("LEGACY_STATUS"), null);
  assert.equal(cashierAmountState(true, true), "incomplete");
  assert.equal(cashierAmountState(true, false), "ready");
  assert.equal(cashierAmountState(false, false), "empty");
  assert.equal(canFinishService(null), false);
  assert.equal(canFinishService("2026-08-01T08:00:00Z"), true);
});

test("the workspaces use the fail-safe policies and defer three columns until there is room", () => {
  for (const source of [doctor, cashier]) {
    assert.match(source, /workspaceStyles\.workspace/);
    assert.match(source, /workspaceStyles\.threeColumn/);
    assert.doesNotMatch(source, /2xl:grid-cols-/);
  }
  assert.match(workspaceCss, /container-type: inline-size/);
  assert.match(workspaceCss, /@container \(min-width: 960px\)/);
  // LUẬT "ĐÃ THU" ĐÃ CHUYỂN XUỐNG BACKEND (04/08/2026).
  //
  // Ba dòng cũ đòi thấy đúng `paidCashierPaymentSeeds` + câu PostgREST đọc bảng
  // payment ngay trong trang. Nay trang gọi /api/v1/cashier/board và toàn bộ
  // việc ghép hoá đơn nằm ở cashier_board_service.py — kèm hai chốt mà bản cũ
  // KHÔNG có: chỉ nhận kind 'thuoc'/'dich_vu', và bỏ phiếu thu đã huỷ
  // (voided_at). Cả hai có test Python riêng.
  //
  // Điều bài kiểm này canh — trang thu ngân không tự bịa trạng thái đã thu —
  // vẫn đúng, và giờ được canh ở nơi thật sự quyết định.
  assert.match(cashierPage, /cashier\/board/);
  assert.doesNotMatch(cashierPage, /\.from\(["']payment["']\)/);
  assert.match(cashier, /cashierAmountState/);
  assert.match(cashier, /amountState === "incomplete"/);
});

test("clinical editor mutations recover from network failures", () => {
  // Mất mạng giữa chừng không được để nút kẹt "Đang ghi…" và phải nói rõ
  // thao tác CHƯA được ghi.
  assert.match(lamViecApi, /catch \{\s*return \{ ok: false, loi: "Mất kết nối — thao tác CHƯA được ghi\." \}/);
  assert.match(khungTep, /CHƯA được lưu/);
});
