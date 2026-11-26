import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const hook = readFileSync(
  new URL("../app/(dashboard)/_lam-viec/phieu-kham/useTinhCachDung.ts", import.meta.url),
  "utf8",
);

test("đề xuất số lượng chỉ dùng kết quả của đúng dữ liệu đang kê", () => {
  assert.match(hook, /JSON\.stringify\(\{\s*visit_id: visitId,/);
  assert.match(hook, /body: goi/);
  assert.match(hook, /setTraLoi\(\{ goi, kq \}\)/);
  assert.match(hook, /traLoi\?\.goi === goi \? traLoi\.kq : null/);
});

test("không nhận đề xuất khi yêu cầu lỗi hoặc đã hết hiệu lực trong lúc đọc", () => {
  assert.match(hook, /if \(bo \|\| !r\.ok\) return;/);
  assert.match(hook, /await r\.json\(\)[^;]*;\s*if \(!bo\) setTraLoi/);
});

test("chọn kiểu dùng không tự điền số liều hoặc ngày chu kỳ", () => {
  const control = readFileSync(
    new URL("../app/(dashboard)/_lam-viec/phieu-kham/CachDungDong.tsx", import.meta.url),
    "utf8",
  );
  assert.match(control, /const chonKieu = [\s\S]+?doi\(\{ kieu: k \}\);\s*\};/);
});
