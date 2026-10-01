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

test("hai phía lấy URL từ CÙNG một nguồn lúc chạy, tên cũ giữ nguyên", async () => {
  // Từ 01/10/2026 URL công khai không nung vào bundle (một ảnh chạy cả staging
  // lẫn prod). Máy chủ và trình duyệt cùng đọc cauHinhCongKhai() — lệch nguồn
  // là tên cookie hai bên lệch nhau, cả phòng khám không đăng nhập được.
  const ma = readFileSync(
    new URL("../lib/supabase-cookie.ts", import.meta.url),
    "utf8",
  ).replace(/\/\/.*$/gm, "");
  assert.match(ma, /hauToTheoCong\(cauHinhCongKhai\(\)\.supabaseUrl\)/);
  assert.match(ma, /"clinicai-auth"\s*\+/, "tiền tố phải giữ nguyên chuỗi cũ");

  const { tenCookieSupabase } = await import("../lib/supabase-cookie.ts");
  const cu = process.env.PUBLIC_SUPABASE_URL;
  process.env.PUBLIC_SUPABASE_URL = "https://dr4women.io.vn";
  assert.equal(tenCookieSupabase(), "clinicai-auth", "prod: tên cũ, không ai bị đăng xuất");
  process.env.PUBLIC_SUPABASE_URL = "http://127.0.0.1:54321";
  assert.equal(tenCookieSupabase(), "clinicai-auth-54321", "đọc LÚC GỌI, không chụp lúc nạp");
  if (cu === undefined) delete process.env.PUBLIC_SUPABASE_URL;
  else process.env.PUBLIC_SUPABASE_URL = cu;
});
