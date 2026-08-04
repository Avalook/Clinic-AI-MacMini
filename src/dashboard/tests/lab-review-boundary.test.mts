import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const read = (path: string) => readFileSync(join(ROOT, path), "utf8");

const triageProxy = read("app/api/lab-result/[id]/triage/route.ts");
const reviewProxy = read("app/api/lab-result/[id]/review/route.ts");
const actions = read("app/(dashboard)/patients/[id]/LabReviewActions.tsx");
const history = read("app/(dashboard)/patients/[id]/PatientHistory.tsx");
const patientPage = read("app/(dashboard)/patients/[id]/page.tsx");
const releaseRule = read("lib/lab-release.ts");

test("both lab safety proxies require a real doctor role", () => {
  for (const source of [triageProxy, reviewProxy]) {
    assert.match(source, /auth\.getUser\(\)/);
    // Chốt nay CHẶT HƠN, không lỏng hơn.
    //
    // `isPhysicianRole` hẹp hơn `isDoctorRole`: nó KHÔNG gồm TKYK (thư ký y
    // khoa nhập hộ bệnh án nhưng không duyệt kết quả xét nghiệm). Bài kiểm này
    // canh "phải là bác sĩ thật"; nhận cả hai tên hàm thì nó vẫn canh đúng điều
    // đó mà không bắt code phải lỏng lại đúng bằng lúc nó được viết.
    assert.match(source, /is(Doctor|Physician)Role\(role\)/);
    assert.match(source, /status:\s*403/);
    assert.doesNotMatch(source, /getSupabaseService|SUPABASE_SERVICE_ROLE_KEY/);
  }
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
  assert.match(patientPage, /canReviewLabs=\{is(Doctor|Physician)Role\(role\)\}/);
});

test("CSKH release remains finalized GROUP_A only", () => {
  assert.match(releaseRule, /triageGroup === "GROUP_A" && isFinalized/);
  // [\s\S] rather than the /s flag: tsconfig targets ES2017, where dotAll is
  // a compile error (TS1501).
  assert.doesNotMatch(releaseRule, /GROUP_B[\s\S]*allowed:\s*true/);
});
