import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");
const vatTuQuay = read("../app/(dashboard)/thu-ngan/VatTuQuay.tsx");
const bangGia = read("../app/(dashboard)/cashier/VatTuBangGia.tsx");
const kieu = read("../lib/vat-tu.ts");

test("quầy: ô nguyên nhân bán thêm gửi kèm mỗi lần thêm, dây BẬT thì khoá nút thêm tới khi đủ chữ", () => {
  assert.match(vatTuQuay, /ly_do_ban: lyDoBan\.trim\(\)/);
  assert.match(vatTuQuay, /goi\.bat_ly_do_ban \? " \(bắt buộc, 5–500 ký tự\)"/);
  // Khoá chỉ là gợi ý cho người bấm — máy chủ vẫn ép (không luật nghiệp vụ trong TSX).
  assert.match(vatTuQuay, /thieuLyDo && !daCoDong\(m\.id\)/);
  assert.match(vatTuQuay, /Nguyên nhân: \{d\.ly_do_ban\}/);
  assert.match(kieu, /bat_ly_do_ban: boolean/);
  assert.match(kieu, /ly_do_ban: string \| null/);
});

test("quầy: người duyệt là người có lego Duyệt vật tư, không còn nói 'quản lý' theo vai", () => {
  assert.match(vatTuQuay, /Trưởng ca \/ Quản lý/);
  assert.match(vatTuQuay, /Bạn có quyền duyệt vật tư/);
  assert.doesNotMatch(vatTuQuay, /Bạn là quản lý/);
  assert.doesNotMatch(vatTuQuay, /Chọn quản lý/);
  // Việc bình thường (cần duyệt) dùng màu trung tính — không vàng/đỏ (Tuyền 14/10).
  assert.doesNotMatch(vatTuQuay, /bg-warning-bg|text-warning/);
  assert.doesNotMatch(bangGia, /tone="warning">Cần/);
});
