// Lưới đặt chỗ không được mời khung nằm NGOÀI ca trực của bác sĩ.
//
// Tuyền 14/08/2026: bấm 07:00 cho Bác sĩ Lê Thiệu Quyết ngày 15/08, ô bấm được
// và tô xanh — rồi máy chủ từ chối: *"chỉ trực 12:00–23:00, không có mặt lúc
// 07:00"*. Hồ sơ bệnh nhân đã kịp tạo, chỉ lịch hẹn hỏng.
//
// GỐC: HAI LƯỚI, BIẾT HAI THỨ KHÁC NHAU.
//
//   BookingHub          hỏi `/appointments/quote?doctor_id=` từng bác sĩ, và
//                       máy chủ chỉ trả về khung TRONG ca → ô nào không có
//                       trong câu trả lời thì ghi "Ngoài ca trực".
//   CinemaSlotPicker    chỉ nhận `dutyDoctorIds` = "ai CÓ ca hôm đó", rồi vẽ
//                       đủ mọi cột 07:00→23:00.
//
// Bác sĩ chỉ trực CHIỀU vẫn qua được `dutyDoctorIds`, nên lưới thứ hai mời đặt
// lúc 7 giờ sáng.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const picker = readFileSync(
  new URL("../app/(dashboard)/patients/CinemaSlotPicker.tsx", import.meta.url),
  "utf8",
);
const form = readFileSync(
  new URL("../app/(dashboard)/patients/new/NewPatientForm.tsx", import.meta.url),
  "utf8",
);
const ma = picker.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");

test("lưới nhận khoảng ca trực và chặn ô nằm ngoài", () => {
  assert.match(ma, /shiftWindows/, "lưới phải nhận khoảng ca của từng bác sĩ");
  assert.match(ma, /const ngoaiCa = !trongCa\(/, "phải tính cờ ngoài-ca cho mỗi ô");
  const dis = /const disabled = [^;]+;/.exec(ma);
  assert.ok(dis, "không tìm thấy chỗ tính `disabled`");
  assert.match(
    dis![0],
    /ngoaiCa/,
    "ô ngoài ca phải KHÔNG bấm được — hiện màu thôi thì vẫn đặt được",
  );
});

test("KHÔNG BIẾT CA THÌ KHÔNG CHẶN", () => {
  // Chốt an toàn quan trọng nhất. Hỏi hụt hay chưa hỏi xong mà đọc thành "ngoài
  // ca" là khoá toàn bộ lịch của một bác sĩ đang thật sự đi làm — sai theo
  // hướng đó tệ hơn hẳn hướng ngược lại, vì máy chủ vẫn còn chặn cứng ở dưới.
  const fn = /function trongCa\([\s\S]*?\n\}/.exec(ma);
  assert.ok(fn, "không tìm thấy hàm trongCa");
  assert.match(
    fn![0],
    /if \(!windows \|\| windows\.length === 0\) return true;/,
    "thiếu ca thì phải cho qua",
  );
});

test("nửa mở [lo, hi) — khung đúng 12:00 thuộc ca CHIỀU", () => {
  // Cùng quy ước với `covers()` bên backend. Dùng `<=` ở vế phải thì khung
  // 12:00 vừa thuộc ca sáng vừa thuộc ca chiều, và hai lưới lệch nhau đúng một
  // khung — kiểu lệch khó thấy nhất.
  const fn = /function trongCa\([\s\S]*?\n\}/.exec(ma);
  assert.match(fn![0], /phut >= lo && phut < hi/, "phải là nửa mở");
});

test("khoảng ca LẤY TỪ BACKEND, không tự quy đổi SÁNG/CHIỀU", () => {
  // Mốc 12:00 là quyết định của phòng khám, nằm ở đúng một hằng số trong
  // `core/shifts.py`. Tự đổi nhãn ca thành giờ ở frontend là dựng bản thứ hai
  // của luật ấy — và bản thứ hai sẽ lệch vào ngày phòng khám đổi mốc.
  assert.match(
    form,
    /appointments\/quote\?date=[\s\S]{0,200}?doctor_id=/,
    "form phải hỏi quote để lấy shift_windows",
  );
  assert.match(form, /shift_windows/, "phải đọc đúng trường của backend");
  for (const cam of [/\bSANG\b/, /\bCHIEU\b/, /12\s*\*\s*60/]) {
    assert.doesNotMatch(
      form.replace(/\/\/.*$/gm, ""),
      cam,
      "form không được tự quy đổi nhãn ca thành giờ",
    );
  }
});

test("lưới nhận được khoảng ca từ form", () => {
  assert.match(
    form,
    /shiftWindows=\{shiftWindows\}/,
    "nạp xong mà không truyền xuống thì bản vá đứng im",
  );
});
