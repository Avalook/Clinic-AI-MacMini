import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");
const KHACH = "../app/(dashboard)/CongTyKhach.tsx";

test("công ty trong hồ sơ khách: route Next chỉ chuyển tiếp, kiểm mã khách / công ty", () => {
  const khach = read("../app/api/hoa-don/cong-ty/khach/[id]/route.ts");
  assert.match(khach, /proxyJsonToBackend\("GET", `\/api\/v1\/hoa-don\/cong-ty\/khach\//);
  assert.match(khach, /proxyJsonToBackend\("PUT", `\/api\/v1\/hoa-don\/cong-ty\/khach\//);
  assert.match(khach, /UUID_RE\.test\(id\)/);
  const an = read("../app/api/hoa-don/cong-ty/an/[id]/route.ts");
  assert.match(an, /proxyJsonToBackend\("PUT", `\/api\/v1\/hoa-don\/cong-ty\/an\//);
  assert.match(an, /UUID_RE\.test\(id\)/);
});

test("khối công ty nằm trong hồ sơ khách (PatientAdminEditor) — dùng chung mọi nơi mở hồ sơ", () => {
  const editor = read("../app/(dashboard)/PatientAdminEditor.tsx");
  assert.match(editor, /import CongTyKhach from "\.\/CongTyKhach"/);
  assert.match(editor, /<CongTyKhach clinicPatientId=\{cur\.clinic_patient_id\} \/>/);
});

test("hồ sơ khách: gỡ = ẩn + khôi phục (hoàn tác), không có quyền → ẩn khối, luật ở máy chủ", () => {
  const ui = read(KHACH);
  assert.match(ui, /Khôi phục/);
  assert.match(ui, /cong-ty\/an\//);
  assert.match(ui, /r\.status === 403/);
  assert.match(ui, /canh_bao_mst/);
  assert.match(ui, /không đổi công ty đã ghi trên các hoá đơn cũ/);
  assert.doesNotMatch(ui, /\[0-9\]\{10\}|\\d\{10\}|window\.confirm|\.reduce\(/);
  assert.doesNotMatch(ui, /<button(?![^>]*type=)/);
});

test("khối trên phiếu và khối trong hồ sơ dùng chung bộ ô FormCongTy (một nơi định nghĩa)", () => {
  assert.match(read("../app/(dashboard)/hoa-don/CongTyHoaDon.tsx"), /import FormCongTy/);
  assert.match(read(KHACH), /import FormCongTy/);
  assert.doesNotMatch(read("../app/(dashboard)/hoa-don/CongTyHoaDon.tsx"), /label: "Tên công ty"|ten: "Tên công ty"/);
});
