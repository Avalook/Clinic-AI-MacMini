import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path: string): string =>
  readFileSync(new URL(path, import.meta.url), "utf8");

const khoi = read("../app/(dashboard)/appointments/LichSapToiCuaKhach.tsx");
const hub = read("../app/(dashboard)/appointments/BookingHub.tsx");
const route = read("../app/api/appointments/route.ts");

// Quang 09/08/2026: *"không có hiện thông báo đó thì đặt vô tội vạ quá, lịch sau
// lại chồng lên lịch trước"*. Cái đắt nhất ở đây KHÔNG phải khối cảnh báo — mà
// là chuyện nó im lặng đúng như lúc khách sạch lịch khi lượt hỏi hỏng.

test("khối cảnh báo phân biệt ĐỦ BỐN trạng thái, không gộp 'hỏng' vào 'chưa có'", () => {
  for (const kind of ["dang-hoi", "hong", "xong"]) {
    assert.match(khoi, new RegExp(`"${kind}"`), `thiếu trạng thái ${kind}`);
  }
  // Hỏi xong mà rỗng thì phải NÓI RA là đã kiểm — im lặng đọc thành "cứ đặt".
  assert.match(khoi, /Đã kiểm: khách chưa có lịch nào sắp tới/);
  // Hỏi hỏng thì phải nói rõ là CHƯA kiểm được, và nói to (role="alert").
  assert.match(khoi, /Chưa kiểm được lịch cũ của khách/);
  assert.match(khoi, /role="alert"/);
});

test("lượt hỏi hỏng được ghi lại là hỏng, không bị nuốt", () => {
  // `.catch(() => {})` rỗng ở đây là đủ để dựng lại đúng lỗi cũ.
  assert.match(hub, /catch\(\(\) => \{\s*if \(con\) setLichDaNap\(\{ khach, ket: \{ ok: false \} \}\)/);
  assert.doesNotMatch(hub, /\.catch\(\(\) => \{\}\)/);
});

test("kết quả gắn với mã khách, và chỉ dùng khi khớp khách đang chọn", () => {
  // Đây là thứ giữ cho panel không mang tên người này mà kèm lịch người kia.
  assert.match(hub, /lichDaNap\?\.khach === selectedPatientId/);
});

test("API trả lịch TỪ BÂY GIỜ trở đi và bỏ lịch đã huỷ", () => {
  assert.match(route, /clinic_patient_id/);
  assert.match(route, /\.gte\("slot_start", new Date\(\)\.toISOString\(\)\)/);
  assert.match(route, /CANCELLED,NO_SHOW,DOCTOR_DECLINED/);
});
