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

test("ô chọn thuốc ở bàn khám chỉ có thuốc còn hàng ở kho / quầy", () => {
  const man = readFileSync(
    new URL("../app/(dashboard)/_lam-viec/phieu-kham/DonThuocPhieu.tsx", import.meta.url),
    "utf8",
  );
  assert.match(man, /mauThuoc\.filter\(\(m\) => m\.con_hang\)/);
  assert.match(man, /locMauThuoc\(coHang, tu\)/);
  assert.doesNotMatch(man, /Danh mục thuốc \(\{mauThuoc\.length\}\)/);
});

test("bàn khám không bắt bác sĩ khai cách dùng theo ô — chỉ hiện số ngày máy tính", () => {
  const man = readFileSync(
    new URL("../app/(dashboard)/_lam-viec/phieu-kham/DonThuocPhieu.tsx", import.meta.url),
    "utf8",
  );
  const lib = readFileSync(new URL("../lib/phieu-kham.ts", import.meta.url), "utf8");
  assert.doesNotMatch(man, /CachDungDong|KinhCuoiCung|Kiểu dùng/);
  assert.match(man, /oNhap\(i, d, "cach_dung", "Cách dùng"/);
  assert.match(man, /Đủ dùng \{dongKetQua\(/);
  // Đơn từ bàn khám không gửi cấu trúc → máy chủ không viết đè chữ bác sĩ.
  assert.doesNotMatch(lib, /cach_dung_ct: d\.cach_dung_ct/);
});
