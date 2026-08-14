// Tên cookie phiên — prod và staging KHÔNG được dùng chung.
//
// Tuyền 14/08/2026: *"chưa có tên miền nên nếu mở 2 tab thì nó bị trùng"*.
//
// CHỖ AI CŨNG ĐOÁN SAI: cookie không phân biệt cổng (RFC 6265 §8.5).
// `http://IP:80` và `http://IP:8080` là hai origin khác nhau với mọi thứ khác —
// CORS, localStorage, service worker — nhưng dùng chung một hũ cookie. Hai môi
// trường đang nằm đúng như thế trên cùng một IP, nên một tên cookie ghim cứng
// nghĩa là đăng nhập staging ghi đè phiên prod.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { hauToTheoCong } from "../lib/supabase-cookie.ts";

test("PROD GIỮ NGUYÊN TÊN CŨ — không đăng xuất ai", () => {
  // Ranh giới quan trọng nhất. Đổi tên cookie của prod là đăng xuất toàn bộ
  // phòng khám giữa giờ khám: cookie cũ thành vô danh, mọi người bị đá về
  // /login cùng lúc. URL prod không có cổng nên phải rơi vào nhánh rỗng.
  assert.equal(hauToTheoCong("http://222.255.215.219"), "");
  assert.equal(hauToTheoCong("http://222.255.215.219:80"), "");
  assert.equal(hauToTheoCong("https://phongkham.example.com"), "");
  assert.equal(hauToTheoCong("https://phongkham.example.com:443"), "");
});

test("staging tách ra bằng cổng", () => {
  assert.equal(hauToTheoCong("http://222.255.215.219:8080"), "-8080");
  assert.equal(hauToTheoCong("http://127.0.0.1:54321"), "-54321");
});

test("URL thiếu hoặc hỏng thì KHÔNG bịa hậu tố", () => {
  // Thà hai môi trường trùng nhau như cũ, còn hơn sinh ra một tên cookie mà
  // phía bên kia không đoán được — lúc ấy đăng nhập báo thành công rồi đá thẳng
  // về /login, và không bên nào coi đó là lỗi.
  assert.equal(hauToTheoCong(undefined), "");
  assert.equal(hauToTheoCong(""), "");
  assert.equal(hauToTheoCong("không-phải-url"), "");
  assert.equal(hauToTheoCong("222.255.215.219:8080"), "", "thiếu scheme");
});

test("đọc biến môi trường ĐÚNG DẠNG Next thay được vào bundle", () => {
  // Next chỉ thay giá trị vào bundle trình duyệt khi thấy nguyên văn
  // `process.env.NEXT_PUBLIC_...`. Gán qua biến trung gian thì phía trình duyệt
  // nhận undefined, tên cookie hai bên lệch nhau, và cả phòng khám không đăng
  // nhập được — đúng lỗi đã mô tả ở đầu lib/supabase-cookie.ts.
  const ma = readFileSync(
    new URL("../lib/supabase-cookie.ts", import.meta.url),
    "utf8",
  ).replace(/\/\/.*$/gm, "");
  assert.match(
    ma,
    /process\.env\.NEXT_PUBLIC_SUPABASE_URL/,
    "phải truy cập nguyên văn, không qua biến trung gian",
  );
  assert.match(ma, /"clinicai-auth"\s*\+/, "tiền tố phải giữ nguyên chuỗi cũ");
});
