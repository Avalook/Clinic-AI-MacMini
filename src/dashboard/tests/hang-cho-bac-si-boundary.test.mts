// Hàng chờ xếp bác sĩ phải bắt CẢ lịch vừa MẤT bác sĩ, không chỉ lịch chưa xếp.
//
// TÌM ĐƯỢC KHI NGHIỆM THU 11/08/2026, bằng phép thử trên staging:
//   1. Chọn một lịch hẹn có bác sĩ, bác sĩ đó đang có ca trực đúng ngày.
//   2. Gỡ ca trực ấy (mô phỏng bác sĩ nghỉ đột xuất).
//   3. Đếm lịch hẹn mồ côi  → 2   (một ca trực, hai khách bị ảnh hưởng)
//   4. Màn "Chờ xếp bác sĩ" → 0   ← lỗ hổng
//
// Vì màn ấy chỉ hỏi `doctor_id IS NULL`, tức lịch *chưa từng* xếp ai. Lịch *vừa
// mất* người thì `doctor_id` vẫn trỏ tới một bác sĩ có thật — chỉ là bác sĩ ấy
// không đi làm hôm đó. Không dòng mã nào khác trong hệ thống đi tìm loại này.
//
// Hậu quả: bác sĩ nghỉ đột xuất → khách vẫn tưởng lịch còn nguyên → đến quầy mới
// vỡ lẽ. Và không ai biết còn bao nhiêu khách nữa cùng cảnh, vì gỡ MỘT ca trực
// thường kéo theo NHIỀU lịch.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const router = readFileSync(
  new URL("../../clinicai/api/v1/routers/booking.py", import.meta.url),
  "utf8",
);

/**
 * Lấy ĐÚNG câu SQL của hàng chờ, bỏ qua docstring.
 *
 * Bản đầu của bài kiểm này cắt mọi chuỗi `"""…"""` để bỏ docstring — và cắt luôn
 * câu SQL, vì SQL cũng nằm trong `"""…"""`. Cả ba phép kiểm đỏ vì lỗi của chính
 * bài kiểm, không phải của mã. Cùng một cái bẫy đã gặp hôm 10/08 khi một bài
 * kiểm khớp phải chính dòng chú thích giải thích lỗi.
 *
 * Nên ở đây cắt theo MỐC MÃ (`conn.fetch(` … `identity.clinic_id`) chứ không cắt
 * theo hình dạng chuỗi: docstring nằm trước `conn.fetch(`, nên nó tự rơi ra ngoài.
 */
function cauSqlHangCho(): string {
  const i = router.indexOf('"/appointments/cho-xep-bac-si"');
  assert.ok(i > 0, "không tìm thấy endpoint hàng chờ");
  const j = router.indexOf("conn.fetch(", i);
  const k = router.indexOf("identity.clinic_id", j);
  assert.ok(j > 0 && k > j, "không tìm thấy khối truy vấn");
  return router.slice(j, k);
}
const view = readFileSync(
  new URL(
    "../app/(dashboard)/appointments/cho-xep-bac-si/HangChoView.tsx",
    import.meta.url,
  ),
  "utf8",
);

test("truy vấn phải hỏi work_roster, không chỉ doctor_id IS NULL", () => {
  const khoi = cauSqlHangCho();
  assert.match(
    khoi,
    /work_roster/,
    "không đối chiếu ca trực ⇒ lịch mất bác sĩ vẫn vô hình",
  );
  assert.match(khoi, /NOT EXISTS/, "phải tìm lịch KHÔNG có ca trực tương ứng");
  assert.match(
    khoi,
    /doctor_id IS NULL/,
    "vẫn phải giữ nhánh cũ — lịch chưa xếp ai",
  );
});

test("mỗi dòng phải nói RÕ vì sao nó nằm ở hàng chờ", () => {
  const sql = cauSqlHangCho();
  assert.match(sql, /'CHUA_XEP'/, "thiếu nhãn cho lịch chưa xếp");
  assert.match(sql, /'MAT_BAC_SI'/, "thiếu nhãn cho lịch mất bác sĩ");
  assert.match(
    sql,
    /bac_si_cu/,
    "phải trả tên bác sĩ đã rời đi — quản lý cần biết còn ai khác cùng cảnh",
  );
});

test("chỉ tính lịch từ BÂY GIỜ trở đi cho nhánh mất bác sĩ", () => {
  // Lịch đã qua mà mất bác sĩ thì không xếp lại được nữa; đưa vào chỉ làm ngập
  // hàng chờ và che mất những cái còn cứu được.
  const khoi = cauSqlHangCho();
  assert.match(khoi, /slot_start >= now\(\)/, "thiếu chặn lịch đã qua");
});

test("giao diện hiện cảnh báo cho lịch mất bác sĩ", () => {
  const ma = view.replace(/\{\/\*[\s\S]*?\*\/\}/g, "");
  assert.match(ma, /MAT_BAC_SI/, "giao diện không phân biệt hai lý do");
  assert.match(
    ma,
    /bac_si_cu/,
    "phải nêu tên bác sĩ đã rời — 'một bác sĩ nào đó' không giúp quản lý xử lý",
  );
  assert.match(
    ma,
    /không còn ca trực/,
    "câu cảnh báo phải nói rõ chuyện gì đã xảy ra",
  );
});
