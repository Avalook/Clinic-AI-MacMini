// Tạo hồ sơ / Thêm khách: CHỈ BẮT BUỘC HỌ TÊN (Tuyền chốt 30/09/2026).
//
// Dấu sao đã bỏ trên giao diện, nhưng save() vẫn chặn ngầm SĐT, giới tính,
// ngày sinh, tỉnh/phường — người trực không biết vì sao Lưu không đi. Quầy
// đông thì họ chỉ kịp ghi tên, sửa phần còn lại sau ở hồ sơ.
//
// Điền rồi thì vẫn phải đúng định dạng (SĐT 10 số, CCCD 12 số, năm sinh).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const form = readFileSync(
  new URL("../app/(dashboard)/patients/new/NewPatientForm.tsx", import.meta.url),
  "utf8",
);
const batDau = form.indexOf("async function save(");
const ketThuc = form.indexOf('fetch("/api/patients"', batDau);
const save = form.slice(batDau, ketThuc);

test("save() chỉ chặn thiếu Họ tên, không chặn thiếu SĐT/giới tính/ngày sinh/địa chỉ", () => {
  assert.ok(batDau > 0 && ketThuc > batDau, "không tìm thấy thân save()");
  assert.match(save, /if \(!fullName\.trim\(\)\)/);
  for (const chan of [
    /if \(!phone\.trim\(\)\)/,
    /if \(!gender\)/,
    /if \(!dobIso\)|else if \(!dobIso\)/,
    /if \(!birthYear\.trim\(\)\)/,
    /if \(!provinceCode\)/,
    /if \(!wardCode\)/,
    /requireAddress/,
  ]) {
    assert.doesNotMatch(save, chan, `save() lại chặn ngầm: ${chan}`);
  }
});

test("chỉ gõ tên, khối lịch trống hết → chỉ lưu hồ sơ, không đòi dịch vụ", () => {
  assert.match(save, /const lichTrong = !serviceId && !apptDate && !apptTime;/);
  assert.match(save, /if \(!walkin && !chuaDatLich && !lichTrong\)/);
});

test("điền rồi thì vẫn kiểm định dạng", () => {
  assert.match(save, /phoneError\(phone\)/);
  assert.match(save, /cccdError\(cccd\)/);
  assert.match(save, /birthYearErr/);
  assert.match(save, /dobErr/);
});

test("giới tính chọn lại được ô trống, gợi ý không còn chữ 'Bắt buộc' ngoài Họ tên", () => {
  // Ô dịch vụ / kênh đặt vẫn giữ "disabled hidden" — đặt lịch thì cần chúng.
  assert.doesNotMatch(form, /<option value="" disabled hidden>— Chọn —<\/option>/);
  assert.match(form, /<option value="">— Chưa rõ —<\/option>/);
  assert.doesNotMatch(form, /Bắt buộc: Họ tên, Ngày sinh/);
});
