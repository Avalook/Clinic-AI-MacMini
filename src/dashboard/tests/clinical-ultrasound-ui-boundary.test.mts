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

// /tasks (DoctorWorkBoard, CashierWorkBoard, CskhActionBoard, ConfirmBoard,
// TasksRealtime) đã gộp 18/09/2026 — màn thu tiền thật là QuayThuNgan.
const cashier = read("../app/(dashboard)/thu-ngan/QuayThuNgan.tsx");
const clinicalForm = read("../app/(dashboard)/tasks/ClinicalRecordForm.tsx");
const serviceForm = read("../app/(dashboard)/tasks/ServiceFormEngine.tsx");
const biometry = read("../app/(dashboard)/tasks/SonoBiometry.tsx");
// Ba màn Lấy mẫu / Thủ thuật / Điều dưỡng siêu âm đã gộp thành MỘT màn phòng
// dịch vụ đọc hàng chờ theo chỉ định (Tuyền chốt 16/09/2026).
const phong = read("../app/(dashboard)/phong/[ma]/PhongDichVu.tsx");
const banKham = read("../app/(dashboard)/ban-kham/BanKham.tsx");
const khungTep = read("../app/(dashboard)/_lam-viec/KhungTep.tsx");
// Một màn điền cho MỌI biểu mẫu — vẽ theo `khung` máy chủ trả về (23/09/2026).
const phieuKetQua = read("../app/(dashboard)/_lam-viec/PhieuKetQua.tsx");
const hangCho = read("../app/(dashboard)/_lam-viec/HangChoCot.tsx");
const lamViecApi = read("../app/(dashboard)/_lam-viec/api.ts");
const statCard = read("../app/(dashboard)/StatCard.tsx");
const workspaceCss = read("../app/(dashboard)/tasks/WorkspacePrimitives.module.css");

test("clinical workspaces expose their reference-style working regions", () => {
  for (const [source, regions] of [
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
    cashier,
    clinicalForm,
    serviceForm,
    biometry,
    statCard,
    phong,
    banKham,
    khungTep,
    hangCho,
    phieuKetQua,
  ]) {
    assert.doesNotMatch(source, /#[0-9a-f]{3,8}/iu);
    assert.doesNotMatch(source, /pink|rose|fuchsia/iu);
    assert.doesNotMatch(source, /rgba\(/iu);
    assert.doesNotMatch(source, /bg-white|bg-(?:red|orange|yellow|blue|green|gray)-/iu);
  }
});

test("redesigning does not replace the established mutation contracts", () => {
  assert.match(banKham, /<ClinicalRecordForm/);
  assert.match(cashier, /fetch\("\/api\/payment"/);
  // Màn phòng và bàn khám ghi qua ĐÚNG MỘT đường: /api/luot-kham.
  assert.match(lamViecApi, /fetch\("\/api\/luot-kham"/);
  for (const src of [phong, banKham]) {
    assert.doesNotMatch(src, /\/api\/(sono|service-log|lab-result|work-items)/);
  }
});

test("phòng dịch vụ: Bắt đầu → phiếu kết quả + tệp → Xong / Không làm được", () => {
  // 23/09/2026: hai lệnh thành NĂM (Lifecycle v1 Slice 5), và nội dung kết quả
  // rời khỏi lệnh "Xong" sang phiếu. Bài kiểm này đổi theo, KHÔNG nới: đường đi
  // vẫn phải là guiThaoTac, và ô tệp vẫn phải có mặt ngay lúc đang làm.
  assert.match(phong, /guiThaoTac/);
  assert.match(phong, /"bat-dau-v1"/);
  assert.match(phong, /"xong-v1"/);
  assert.match(phong, /"khong-lam-v1"/);
  assert.match(phong, /"gian-doan-v1"/);
  assert.match(phong, /"lam-lai-v1"/);
  assert.match(phong, /ly_do: lyDo/);
  assert.match(phong, /<KhungTep/);
  assert.match(phong, /<PhieuKetQua/);
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

test("the shared workspace grid still defers three columns until there is room", () => {
  assert.match(workspaceCss, /container-type: inline-size/);
  assert.match(workspaceCss, /@container \(min-width: 960px\)/);
  // Trang thu ngân không tự bịa trạng thái đã thu: nó hỏi máy chủ
  // (/api/cashier → cashier_board_service.py), không đọc bảng payment.
  assert.match(cashier, /\/api\/cashier\?modes=/);
  assert.doesNotMatch(cashier, /\.from\(["']payment["']\)/);
});

test("clinical editor mutations recover from network failures", () => {
  // Mất mạng giữa chừng không được để nút kẹt "Đang ghi…" và phải nói rõ
  // thao tác CHƯA được ghi.
  // Đợt 3: kèm `status: 0` để tự lưu biết đây là lỗi mạng (thử lại).
  assert.match(
    lamViecApi,
    /catch \{\s*return \{ ok: false, loi: "Mất kết nối — thao tác CHƯA được ghi\.", status: 0 \}/,
  );
  assert.match(khungTep, /CHƯA được lưu/);
});
