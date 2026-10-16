// Form TẠO khách (NewPatientForm — `/patients/new` VÀ tab "Thêm" của `/appointments`)
// có ô "Email (nếu có)" cạnh CCCD (Tuyền 16/10/2026: "Hiện hệ thống … chưa có
// trường email"). Không bắt buộc (luật 30/09: chỉ bắt buộc Họ tên); điền thì kiểm
// định dạng; rỗng thì KHÔNG gửi khoá; gửi qua `POST /api/patients` → FastAPI.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { emailError } from "../lib/validation.ts";

const form = readFileSync(
  new URL("../app/(dashboard)/patients/new/NewPatientForm.tsx", import.meta.url),
  "utf8",
);
const batDau = form.indexOf("async function save(");
const ketThuc = form.indexOf('fetch("/api/patients"', batDau);
const save = form.slice(batDau, ketThuc);
const bodyPost = form.slice(ketThuc, form.indexOf("const json = await res.json();", ketThuc));

test("có ô Email (nếu có) kiểu email, đặt ngay sau ô CCCD", () => {
  const cccd = form.indexOf("CCCD (nếu cung cấp)");
  const mail = form.indexOf("Email (nếu có)");
  const coSo = form.indexOf("Cơ sở đăng ký khám", cccd);
  assert.ok(cccd > 0 && mail > cccd && coSo > mail, "ô Email phải nằm giữa CCCD và Cơ sở");
  assert.match(form, /<input\s+type="email"\s+value=\{email\}/);
  assert.match(form, /onChange=\{\(e\) => setEmail\(e\.target\.value\)\}/);
});

test("Email không bắt buộc; điền thì kiểm bằng emailError của lib/validation", () => {
  assert.match(form, /emailError,/, "phải import emailError từ lib/validation");
  assert.match(save, /emailError\(email\)/);
  assert.doesNotMatch(save, /if \(!email\.trim\(\)\)/, "save() không được chặn khi thiếu email");
  assert.match(form, /const emailErr = emailError\(email\);/);
});

test("gửi đúng khoá `email` cho /api/patients; rỗng thì bỏ khoá", () => {
  assert.ok(batDau > 0 && ketThuc > batDau, "không tìm thấy thân save()");
  assert.match(bodyPost, /email: email\.trim\(\) \|\| undefined,/);
  assert.match(bodyPost, /national_id_number: cccd,/);
});

test("'Dùng bệnh nhân này' / trùng SĐT không ghi gì vào hồ sơ cũ (không ghi đè email)", () => {
  assert.doesNotMatch(form, /method:\s*"PATCH"[^}]*\/api\/patients/);
  assert.match(form, /onClick=\{\(\) => proceed\(m\.clinic_patient_id\)\}/);
});

test("route POST /api/patients chặn email sai bằng 400 tiếng Việt, đường 'email' đi thẳng sang FastAPI", () => {
  const route = readFileSync(new URL("../app/api/patients/route.ts", import.meta.url), "utf8");
  const post = route.slice(route.indexOf("export async function POST"), route.indexOf("export async function PATCH"));
  assert.match(post, /emailError\(String\(body\.email \?\? ""\)\)/);
  assert.match(post, /body: JSON\.stringify\(body\)/, "POST phải chuyển nguyên body (có email) cho FastAPI");
});

test("email nằm trong bản nháp tự lưu (khôi phục lại được)", () => {
  assert.match(form, /phone, phone2, cccd, email,/);
  assert.match(form, /setEmail\(chu\("email"\)\)/);
});

test("emailError: rỗng hợp lệ; sai định dạng báo tiếng Việt", () => {
  assert.equal(emailError(""), null);
  assert.equal(emailError("   "), null);
  assert.equal(emailError(null), null);
  assert.equal(emailError(" Mai.Lan@Example.com "), null);
  for (const rac of ["khong-phai-email", "abc@", "@domain.com", "a b@c.com", "a@b"]) {
    assert.equal(emailError(rac), "Email không đúng định dạng.", rac);
  }
  assert.equal(emailError("a".repeat(250) + "@b.com"), "Email không đúng định dạng.");
});
