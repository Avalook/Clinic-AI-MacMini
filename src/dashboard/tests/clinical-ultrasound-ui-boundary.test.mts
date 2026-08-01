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
const lab = read("../app/(dashboard)/lab-queue/LabQueueView.tsx");
const service = read("../app/(dashboard)/service-queue/ServiceQueueView.tsx");
const sono = read("../app/(dashboard)/sono/SonoView.tsx");
const cashierPage = read("../app/(dashboard)/tasks/page.tsx");
const statCard = read("../app/(dashboard)/StatCard.tsx");
const workspaceCss = read("../app/(dashboard)/tasks/WorkspacePrimitives.module.css");

test("clinical workspaces expose their reference-style working regions", () => {
  for (const [source, regions] of [
    [doctor, ["Hàng đợi khám bệnh", "Lịch khám và hồ sơ", "Điều phối lượt khám"]],
    [cashier, ["Danh sách khoản thu", "Chi tiết khoản thu", "Trạng thái thanh toán"]],
    [lab, ["Danh sách xét nghiệm", "Nhập kết quả xét nghiệm", "Kết quả đã trả"]],
    [service, ["Danh sách dịch vụ", "Thực hiện dịch vụ", "Dịch vụ đã hoàn tất"]],
    [sono, ["Điều phối yêu cầu siêu âm", "Hàng đợi siêu âm", "Chi tiết yêu cầu siêu âm"]],
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
    lab,
    service,
    sono,
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
  assert.match(lab, /fetch\("\/api\/lab-result"/);
  assert.match(service, /fetch\("\/api\/service-log"/);
  assert.match(sono, /fetch\("\/api\/sono"/);
});

test("ultrasound keeps its real SA and laboratory workflow boundaries", () => {
  for (const label of ["Bắt đầu", "Hoàn tất", "Hủy", "Lấy mẫu", "Gửi lab", "Có KQ"]) {
    assert.match(sono, new RegExp(label));
  }
  assert.match(sono, /onAction\("start"\)/);
  assert.match(sono, /onAction\("finish"\)/);
  assert.match(sono, /send\("PATCH", \{ id: selected\.id, action \}\)/);
  assert.match(sono, /onToggle\("sample", value\)/);
  assert.match(sono, /onToggle\("sendlab", value\)/);
  assert.match(sono, /onToggle\("result", value\)/);
  assert.match(sono, /send\("PATCH", \{ id: selected\.id, milestone, value \}\)/);
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
  for (const source of [doctor, cashier, lab, service, sono]) {
    assert.match(source, /workspaceStyles\.workspace/);
    assert.match(source, /workspaceStyles\.threeColumn/);
    assert.doesNotMatch(source, /2xl:grid-cols-/);
  }
  assert.match(workspaceCss, /container-type: inline-size/);
  assert.match(workspaceCss, /@container \(min-width: 960px\)/);
  assert.match(cashierPage, /paidCashierPaymentSeeds/);
  assert.match(cashierPage, /select\("visit_id, kind, status"\)/);
  assert.match(cashierPage, /\.eq\("status", "PAID"\)/);
  assert.match(cashier, /cashierAmountState/);
  assert.match(cashier, /amountState === "incomplete"/);
  assert.match(service, /canFinishService/);
  assert.match(service, /\{canFinish \? \(/);
  assert.match(sono, /resolveSaWorkflowStatus/);
  assert.match(sono, /sonoPatientDisplayName/);
  assert.match(sono, /status !== null && !done/);
  assert.match(sono, /const selectedUnknownSaStatus =/);
  assert.match(sono, /disabled=\{busy \|\| selectedUnknownSaStatus\}/);
});

test("clinical editor mutations recover from network failures", () => {
  assert.match(lab, /catch \{/);
  assert.match(lab, /finally \{\s*setBusy\(false\);/);
  assert.equal(
    service.match(/finally \{\s*setBusy\(false\);/g)?.length,
    2,
    "service action and creation must both release their busy state",
  );
  assert.match(sono, /catch \{/);
  assert.match(sono, /finally \{\s*setBusy\(false\);/);
});
