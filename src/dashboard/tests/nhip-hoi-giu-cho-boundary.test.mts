// Nhịp hỏi "ai đang giữ chỗ" — con số này LÀ độ trễ mà người dùng cảm nhận.
//
// Đo trên staging 14/08/2026: máy chủ thấy một chỗ giữ mới sau 27–40ms. Nghĩa
// là màn hình bên cạnh chậm KHÔNG PHẢI vì máy chủ, mà vì nó chỉ hỏi lại theo
// nhịp — 15s cho ra trung bình 8 giây, chậm nhất 16 giây.
//
// Tuyền chốt hạ xuống 5s. Giá đã đo, không ước lượng: 4,8ms một nhịp cả chuỗi,
// bốn CSKH cùng mở màn = 0,4% một lõi.
//
// Bài kiểm này giữ con số khỏi trôi ngược, và giữ luôn hai chốt đi kèm — thiếu
// chúng thì hạ nhịp chỉ là tốn thêm lượt gọi.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const nguon = readFileSync(
  new URL("../app/(dashboard)/appointments/BookingHub.tsx", import.meta.url),
  "utf8",
);
const ma = nguon.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");

test("nhịp hỏi chỗ giữ là 5 giây, không chậm hơn", () => {
  const khop = ma.match(/setInterval\(\s*load\s*,\s*(\d+)\s*\)/);
  assert.ok(khop, "không tìm thấy nhịp hỏi chỗ giữ");
  const nhip = Number(khop![1]);
  assert.ok(
    nhip <= 5000,
    `nhịp ${nhip}ms — người bên cạnh sẽ biết sau trung bình ${nhip / 2000}s. ` +
      "Máy chủ trả lời trong 40ms; chậm là do nhịp này, không do máy chủ.",
  );
  assert.ok(
    nhip >= 2000,
    `nhịp ${nhip}ms là quá dày: mỗi nhịp gọi GoTrue xác minh token rồi mới ` +
      "tới FastAPI, nên nó không rẻ như một truy vấn đơn lẻ.",
  );
});

test("quay lại tab thì hỏi lại ngay, không chờ hết nhịp", () => {
  // Trình duyệt bóp nhịp của tab bị ẩn. Không có chốt này thì người vừa quay
  // lại màn hình nhìn vào một bản đồ chỗ giữ cũ — đúng lúc họ tin nó nhất.
  assert.match(ma, /visibilitychange/, "thiếu chốt hỏi lại khi tab hiện lại");
  assert.match(
    ma,
    /removeEventListener\(\s*["']visibilitychange["']/,
    "phải gỡ listener lúc rời màn, nếu không mỗi lần đổi ngày lại chồng thêm một cái",
  );
});

test("đọc chỗ giữ hỏng thì GIỮ bản đồ cũ, không xoá sạch", () => {
  // Ranh giới quan trọng nhất của cả tính năng. Xoá sạch khi lỗi mạng nghĩa là
  // mọi ô đột ngột hiện "còn trống" — một câu khẳng định sai, và là câu đúng
  // kiểu để gây đặt trùng. Nhịp dày gấp ba thì cũng gấp ba cơ hội gặp lỗi mạng.
  const khoi = /const load = \(\)[\s\S]*?\n    const t = setTimeout/.exec(nguon);
  assert.ok(khoi, "không tìm thấy hàm đọc chỗ giữ");
  const bat = /\.catch\(\(\) => \{([\s\S]*?)\}\)/.exec(khoi![0]);
  assert.ok(bat, "hàm đọc chỗ giữ phải bắt lỗi");
  assert.doesNotMatch(
    bat![1],
    /setHeldByOthers/,
    "lỗi mạng KHÔNG được đụng vào bản đồ chỗ giữ",
  );
});
