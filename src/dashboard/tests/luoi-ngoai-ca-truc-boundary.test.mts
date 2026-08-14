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
  const hook = readFileSync(
    new URL("../app/(dashboard)/patients/dung-khoang-ca.ts", import.meta.url),
    "utf8",
  );
  assert.match(
    hook,
    /appointments\/quote\?date=[\s\S]{0,200}?doctor_id=/,
    "hook phải hỏi quote để lấy shift_windows",
  );
  assert.match(hook, /shift_windows/, "phải đọc đúng trường của backend");
  for (const cam of [/\bSANG\b/, /\bCHIEU\b/, /12\s*\*\s*60/]) {
    assert.doesNotMatch(
      hook.replace(/\/\/.*$/gm, ""),
      cam,
      "form không được tự quy đổi nhãn ca thành giờ",
    );
  }
});

test("MỌI chỗ gọi lưới đều nhận khoảng ca", () => {
  // BÀI HỌC 14/08/2026. `CinemaSlotPicker` có BA chỗ gọi: hai trong biểu mẫu
  // khách mới (vãng lai + đặt lịch đầy đủ) và một ở AppointmentBooking. Bản vá
  // đầu chỉ truyền cho MỘT — đúng cái lưới Tuyền không dùng. Test xanh, deploy
  // xanh, lỗi y nguyên trên màn hình.
  //
  // Nên bài kiểm này đếm: bao nhiêu chỗ gọi thì bấy nhiêu chỗ nhận.
  const nguon = [
    ["NewPatientForm", form],
    [
      "AppointmentBooking",
      readFileSync(
        new URL("../app/(dashboard)/patients/AppointmentBooking.tsx", import.meta.url),
        "utf8",
      ),
    ],
  ] as const;
  for (const [ten, ma] of nguon) {
    const goi = (ma.match(/<CinemaSlotPicker/g) ?? []).length;
    const nhan = (ma.match(/shiftWindows=\{shiftWindows\}/g) ?? []).length;
    assert.equal(
      nhan,
      goi,
      `${ten}: ${goi} lưới nhưng chỉ ${nhan} lưới nhận khoảng ca — lưới thiếu ` +
        "sẽ mời đặt ngoài ca trực rồi máy chủ từ chối lúc lưu",
    );
  }
});

test("logic hỏi khoảng ca nằm ở MỘT chỗ", () => {
  // Hai component cùng cần nó. Chép hai bản là hẹn ngày chúng lệch nhau — và
  // bản lệch sẽ im lặng, đúng như lần vừa rồi.
  for (const ma of [form, readFileSync(
    new URL("../app/(dashboard)/patients/AppointmentBooking.tsx", import.meta.url),
    "utf8",
  )]) {
    assert.match(ma, /useKhoangCa\(/, "phải dùng hook chung");
  }
});
