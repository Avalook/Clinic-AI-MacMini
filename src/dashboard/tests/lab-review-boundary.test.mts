// Kết quả xét nghiệm có đúng một cổng an toàn: `requires_doctor_review` mở,
// `is_finalized` đóng, và chỉ chữ ký bác sĩ mới lật được nó (lib/lab-release.ts).
// B.4 thêm hướng ngược lại — "trả lại chỉnh sửa" — nên có hai cách mới làm hỏng
// cổng đó, và cả hai đều im lặng:
//
//  1. Trả lại mà đụng vào hàng lab_result → hoặc sửa bằng chứng, hoặc (tệ hơn)
//     lỡ tay hạ requires_doctor_review và kết quả chưa ai duyệt chạy tới CSKH.
//  2. Hàng rào vai ở frontend rộng hơn backend → TKYK thấy nút, bấm nhận 403.
//     Đây là bug đã có thật trước B.4: patients/[id]/page.tsx dùng isDoctorRole,
//     mà isDoctorRole gồm TKYK còn _REVIEW_GUARD thì không.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const BACKEND = join(ROOT, "..", "clinicai");
const read = (path: string) => readFileSync(join(ROOT, path), "utf8");

const triageProxy = read("app/api/lab-result/[id]/triage/route.ts");
const reviewProxy = read("app/api/lab-result/[id]/review/route.ts");
const sendBackProxy = read("app/api/lab-result/[id]/send-back/route.ts");
const actions = read("app/(dashboard)/patients/[id]/LabReviewActions.tsx");
const history = read("app/(dashboard)/patients/[id]/PatientHistory.tsx");
const patientPage = read("app/(dashboard)/patients/[id]/page.tsx");
const releaseRule = read("lib/lab-release.ts");
const rolesSource = read("lib/roles.ts");
const reviewBoard = read("app/(dashboard)/result-review/ResultReviewBoard.tsx");
const reviewPage = read("app/(dashboard)/result-review/page.tsx");
const safetyService = readFileSync(
  join(BACKEND, "services", "lab_safety_service.py"),
  "utf8",
);
const identitySource = readFileSync(
  join(BACKEND, "api", "identity.py"),
  "utf8",
);
const labRouter = readFileSync(
  join(BACKEND, "api", "v1", "routers", "lab.py"),
  "utf8",
);
const orderService = readFileSync(
  join(BACKEND, "services", "lab_order_service.py"),
  "utf8",
);

test("all three lab safety proxies authenticate and refuse by role", () => {
  for (const source of [triageProxy, reviewProxy, sendBackProxy]) {
    assert.match(source, /auth\.getUser\(\)/);
    assert.match(source, /status:\s*403/);
    assert.doesNotMatch(source, /getSupabaseService|SUPABASE_SERVICE_ROLE_KEY/);
  }
  // Phân loại (triage) là việc ghi lâm sàng — _TRIAGE_GUARD ở lab.py rộng hơn.
  // Ký duyệt và trả lại là chữ ký bác sĩ — hẹp hơn, và phải hẹp GIỐNG NHAU:
  // cùng một quyết định nhìn từ hai phía.
  assert.match(triageProxy, /isDoctorRole\(role\)/);
  for (const source of [reviewProxy, sendBackProxy]) {
    assert.match(source, /canReviewLabResult\(role\)/);
    assert.doesNotMatch(source, /isDoctorRole\(role\)/);
  }
});

test("frontend and backend agree on who may sign or reject a result", () => {
  const backendSet = identitySource.match(/^DOCTOR_ROLES = frozenset\((.*)\)$/m);
  assert.ok(backendSet, "DOCTOR_ROLES không còn ở api/identity.py");
  const backendRoles = [...backendSet[1].matchAll(/ClinicRole\.([A-Z_]+)/g)]
    .map((m) => m[1])
    .sort();

  const helper = rolesSource.match(
    /export function canReviewLabResult\([\s\S]*?\n\}/,
  );
  assert.ok(helper, "roles.ts không còn canReviewLabResult");
  const frontendRoles = [...helper[0].matchAll(/role === "([A-Z_]+)"/g)]
    .map((m) => m[1])
    .sort();

  assert.ok(backendRoles.length > 0, "Không đọc được vai nào từ DOCTOR_ROLES.");
  assert.deepEqual(
    frontendRoles,
    backendRoles,
    "canReviewLabResult phải trùng DOCTOR_ROLES của backend. Rộng hơn = nút " +
      "hiện ra rồi trả 403 (đúng bug TKYK trước B.4); hẹp hơn = bác sĩ mất nút.",
  );

  // Cả hai endpoint đứng sau đúng một guard.
  assert.equal(
    (labRouter.match(/Depends\(_REVIEW_GUARD\)/g) ?? []).length,
    2,
    "Duyệt và trả lại phải cùng đi qua _REVIEW_GUARD.",
  );
});

test("sending a result back never touches the result row", () => {
  const body = safetyService.match(
    /async def send_back_for_correction\([\s\S]*?(?=\n\n(?:async )?def )/,
  );
  assert.ok(body, "send_back_for_correction không còn ở lab_safety_service.py");

  // Chỉ được đọc lab_result (SELECT ... FOR UPDATE để khoá hàng). Một câu UPDATE
  // ở đây là cách rẻ nhất để biến "trả lại" thành đường phát hành: hạ
  // requires_doctor_review xuống false thì kết quả chưa ai ký sẽ lọt qua
  // lib/lab-release.ts.
  assert.doesNotMatch(
    body[0],
    /UPDATE\s+lab_result/i,
    "Trả lại chỉnh sửa đang ghi vào lab_result — cổng an toàn không còn đóng.",
  );
  assert.doesNotMatch(
    body[0],
    /requires_doctor_review\s*=|is_finalized\s*=/,
    "Trả lại chỉnh sửa đang đặt lại cờ an toàn của kết quả.",
  );
  assert.match(body[0], /FOR UPDATE/);
  assert.match(body[0], /INSERT INTO staff_task/);
  // Kết quả đã ký thì không rút lại bằng đường này (409, không phải 404).
  assert.match(body[0], /ConflictError/);
});

test("the fix task is opened once and closed by the fix itself", () => {
  const body = safetyService.match(
    /async def send_back_for_correction\([\s\S]*?(?=\n\n(?:async )?def )/,
  );
  assert.ok(body);
  // Bấm hai lần không mở hai việc: tìm việc đang mở trước khi INSERT.
  assert.match(body[0], /already_open=True/);
  assert.match(body[0], /IN \('PENDING', 'IN_PROGRESS'\)/);

  // Và nhập lại kết quả phải đóng việc đó. Không đóng thì danh sách của phòng
  // xét nghiệm đầy việc đã làm xong, rồi người ta thôi không đọc nó nữa.
  assert.match(orderService, /SEND_BACK_TASK_TYPE/);
  assert.match(
    orderService,
    /UPDATE staff_task[\s\S]{0,400}?status = 'DONE'/,
    "enter_result không còn đóng việc LAB_RESULT_FIX đang mở.",
  );
});

test("the send-back proxy mirrors the backend's minimum reason", () => {
  const backendMin = safetyService.match(/^MIN_SEND_BACK_REASON = (\d+)$/m);
  assert.ok(backendMin, "MIN_SEND_BACK_REASON không còn ở lab_safety_service.py");
  const proxyMin = sendBackProxy.match(/^const MIN_REASON = (\d+);$/m);
  assert.ok(proxyMin, "send-back route không còn MIN_REASON");
  assert.equal(
    proxyMin[1],
    backendMin[1],
    "Ngưỡng ở proxy chỉ để báo lỗi bằng tiếng người. Lệch xuống dưới backend " +
      "thì lời hứa 'đã gửi' hoá ra là 422 mà người bấm không thấy.",
  );

  assert.match(
    sendBackProxy,
    /proxyJsonToBackend\(\s*"POST",\s*`\/api\/v1\/lab\/results\/\$\{id\}\/send-back`/,
  );
  assert.match(sendBackProxy, /clinic_patient_id:\s*clinicPatientId/);
});

test("Next proxies expose only triage and patient-bound review contracts", () => {
  assert.match(
    triageProxy,
    /proxyJsonToBackend\("POST", `\/api\/v1\/lab\/triage\/\$\{id\}`/,
  );
  assert.match(
    reviewProxy,
    /proxyJsonToBackend\(\s*"POST",\s*`\/api\/v1\/lab\/results\/\$\{id\}\/review`/,
  );
  assert.match(reviewProxy, /clinic_patient_id:\s*clinicPatientId/);
});

test("doctor UI cannot fabricate or edit a laboratory result", () => {
  assert.match(actions, /Phân loại an toàn/);
  assert.match(actions, /Duyệt & hoàn tất/);
  assert.match(actions, /window\.confirm/);
  assert.doesNotMatch(
    actions,
    /result_value|result_numeric|result_link|external_ref|<input|<textarea/,
  );
  assert.match(history, /<LabReviewActions/);
  assert.match(history, /canReviewLabs/);
  assert.match(patientPage, /canReviewLabs=\{canReviewLabResult\(role\)\}/);
});

test("the review queue writes through the proxies, not Supabase", () => {
  // Màn /result-review mở cho cả TKYK / Quản lý / Trưởng ca xem hàng đợi, nên
  // nút phải theo canReview chứ không theo việc mở được màn.
  assert.match(reviewPage, /canReviewLabResult\(await getClinicRole\(\)\)/);
  assert.match(reviewPage, /canReview=\{canReview\}/);
  assert.match(reviewBoard, /canReview \?/);

  assert.doesNotMatch(reviewBoard, /\.from\(|getSupabaseService|createClient/);
  assert.match(reviewBoard, /\/api\/lab-result\/\$\{[\w.]+\}\/review/);
  assert.match(reviewBoard, /\/api\/lab-result\/\$\{[\w.]+\}\/send-back/);
  // Ký duyệt là hành động một chiều — hỏi lại trước khi ký.
  assert.match(reviewBoard, /window\.confirm/);
  // Và danh sách phải nạp lại từ server, không tự giấu dòng vừa xử lý.
  assert.match(reviewBoard, /router\.refresh\(\)/);
});

test("CSKH release remains finalized GROUP_A only", () => {
  assert.match(releaseRule, /triageGroup === "GROUP_A" && isFinalized/);
  // [\s\S] rather than the /s flag: tsconfig targets ES2017, where dotAll is
  // a compile error (TS1501).
  assert.doesNotMatch(releaseRule, /GROUP_B[\s\S]*allowed:\s*true/);
});
