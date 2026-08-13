// Màn hình phải hiện CÂU, không hiện MÃ.
//
// Thân lỗi của backend luôn có hai trường (main.py:342, 380):
//
//     {"error": "CONFLICT_ERROR", "message": "Khung giờ đã đầy: tối đa 2 chỗ…"}
//
// `error` là mã cho máy đọc; `message` là câu cho người đọc. Đọc `error` trước
// thì mọi lỗi nghiệp vụ đều biến thành một chuỗi in hoa không nói gì.
//
// ĐO ĐƯỢC, KHÔNG PHẢI SUY ĐOÁN. Ngày 14/08/2026, ba tài khoản CSKH thử cùng
// bấm đặt vào chỗ cuối của một bác sĩ trên staging: một lệnh 201, hai lệnh 409
// — chốt chặn chạy đúng. Nhưng thân lỗi 409 ấy đi qua BookingHub và người thua
// nhìn thấy đúng chữ "CONFLICT_ERROR".
//
// Cùng họ với lỗi đã vá 13/08 (backend nói "không tìm thấy nhân viên", màn hình
// dịch thành "máy chủ hỏng"). Lần đó vá một chỗ; bài kiểm này giữ cho cả hai
// chỗ còn lại không trượt về.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const MAN_HINH = [
  "app/(dashboard)/appointments/BookingHub.tsx",
  "app/(dashboard)/nhan-su/NhanSuBoard.tsx",
];

for (const duong of MAN_HINH) {
  const ma = readFileSync(new URL(`../${duong}`, import.meta.url), "utf8")
    .replace(/\/\/.*$/gm, "")
    .replace(/\/\*[\s\S]*?\*\//g, "");

  test(`${duong}: đọc message trước error`, () => {
    const chuoi = ma.match(/err\.\w+(?:\s*\|\|\s*err\.\w+)+/g) ?? [];
    assert.ok(chuoi.length > 0, "không tìm thấy chỗ dựng câu lỗi");
    for (const c of chuoi) {
      const thu_tu = [...c.matchAll(/err\.(\w+)/g)].map((m) => m[1]);
      const viTriMessage = thu_tu.indexOf("message");
      const viTriError = thu_tu.indexOf("error");
      if (viTriMessage === -1 || viTriError === -1) continue;
      assert.ok(
        viTriMessage < viTriError,
        `"${c}" — đọc mã máy trước câu người đọc; người dùng sẽ thấy ` +
          `"CONFLICT_ERROR" thay cho "Khung giờ đã đầy…"`,
      );
    }
  });
}

test("thân lỗi của backend đúng là {error, message}", () => {
  // Bài kiểm trên chỉ đúng khi backend thật sự trả hai trường ấy. Nếu ai đó đổi
  // tên trường ở backend thì phía màn hình sẽ rơi về câu mặc định — im lặng và
  // vô dụng — nên chốt luôn hình dạng thân lỗi ở đây.
  const main = readFileSync(
    new URL("../../clinicai/main.py", import.meta.url),
    "utf8",
  );
  assert.match(
    main,
    /"error":\s*"CONFLICT_ERROR",\s*\n?\s*"message":/,
    "thân lỗi 409 phải giữ nguyên cặp {error, message}",
  );
});
