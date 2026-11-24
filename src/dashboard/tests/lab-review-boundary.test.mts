import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const read = (path: string) => readFileSync(join(ROOT, path), "utf8");

// 24/11/2026: proxy `lab-result/[id]/triage` + cửa backend `/lab/triage` (AI phân
// nhóm qua LangGraph) đã gỡ — không màn nào gọi. Còn proxy duyệt kết quả.
const reviewProxy = read("app/api/lab-result/[id]/review/route.ts");
const releaseRule = read("lib/lab-release.ts");

test("lab review proxy requires login and leaves authority to the backend", () => {
  // 27/09/2026 (kiểm toán cửa quyền): proxy KHÔNG còn tự gác bằng vai "bác sĩ".
  // Cửa vai ở đây chặn người đã được cấp khối duyệt kết quả, trong khi backend
  // vốn đã hỏi QUYỀN — hai cửa, hai luật, lệch nhau. Nay proxy chỉ kiểm đăng
  // nhập; quyền là của lab.py (bài dưới canh backend vẫn gác).
  assert.match(reviewProxy, /auth\.getUser\(\)/);
  assert.doesNotMatch(reviewProxy, /vaiLamViec|is(Doctor|Physician)Role\(/);
  assert.doesNotMatch(reviewProxy, /getSupabaseService|SUPABASE_SERVICE_ROLE_KEY/);
  const lab = readFileSync(join(ROOT, "../clinicai/api/v1/routers/lab.py"), "utf8");
  // Duyệt = quyền duyệt kết quả.
  assert.match(lab, /_REVIEW_GUARD = cua_quyen\(\s*"result\.review\.approve"/);
  assert.match(lab, /Depends\(_REVIEW_GUARD\)/);
});

test("Next proxy exposes only the patient-bound review contract", () => {
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
