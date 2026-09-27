import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const read = (path: string) => readFileSync(join(ROOT, path), "utf8");

const triageProxy = read("app/api/lab-result/[id]/triage/route.ts");
const reviewProxy = read("app/api/lab-result/[id]/review/route.ts");
const releaseRule = read("lib/lab-release.ts");

test("both lab safety proxies require login and leave authority to the backend", () => {
  // 27/09/2026 (kiểm toán cửa quyền): proxy KHÔNG còn tự gác bằng vai "bác sĩ".
  // Cửa vai ở đây chặn người đã được cấp khối duyệt kết quả, trong khi backend
  // vốn đã hỏi QUYỀN — hai cửa, hai luật, lệch nhau. Nay proxy chỉ kiểm đăng
  // nhập; quyền là của lab.py (bài dưới canh backend vẫn gác).
  for (const source of [triageProxy, reviewProxy]) {
    assert.match(source, /auth\.getUser\(\)/);
    assert.doesNotMatch(source, /vaiLamViec|is(Doctor|Physician)Role\(/);
    assert.doesNotMatch(source, /getSupabaseService|SUPABASE_SERVICE_ROLE_KEY/);
  }
  const lab = readFileSync(join(ROOT, "../clinicai/api/v1/routers/lab.py"), "utf8");
  // Duyệt = quyền duyệt kết quả; phân loại = quyền ghi y khoa.
  assert.match(lab, /_REVIEW_GUARD = cua_quyen\(\s*"result\.review\.approve"/);
  assert.match(lab, /_TRIAGE_GUARD = cua_ghi_y_khoa/);
  assert.match(lab, /Depends\(_REVIEW_GUARD\)/);
  assert.match(lab, /Depends\(_TRIAGE_GUARD\)/);
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

// "doctor UI cannot fabricate…" gỡ 27/09/2026: trang /patients/[id] (nơi duy nhất
// có LabReviewActions) đã gộp vào Danh sách bệnh nhân.

test("CSKH release remains finalized GROUP_A only", () => {
  assert.match(releaseRule, /triageGroup === "GROUP_A" && isFinalized/);
  // [\s\S] rather than the /s flag: tsconfig targets ES2017, where dotAll is
  // a compile error (TS1501).
  assert.doesNotMatch(releaseRule, /GROUP_B[\s\S]*allowed:\s*true/);
});
