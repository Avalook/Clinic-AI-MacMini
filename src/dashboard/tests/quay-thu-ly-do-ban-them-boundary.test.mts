// NGUYÊN NHÂN BÁN THÊM thuộc về DÒNG VỪA THÊM (14/10/2026, bấm thật staging):
// thêm Mirena với lý do A, bấm tiếp đầu dò Bio → dòng Bio mang NGUYÊN lý do A
// vì ô không được xoá. Sai dấu vết. Khoá: thêm xong (thẳng hoặc qua ô duyệt)
// thì xoá ô; thêm HỎNG thì giữ lại để bấm lại không phải gõ lại.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const vatTu = readFileSync(
  new URL("../app/(dashboard)/thu-ngan/VatTuQuay.tsx", import.meta.url),
  "utf8",
);

/** Thân hàm `async function <ten>(` tới hàm kế tiếp. */
function than(ten: string): string {
  const dau = vatTu.indexOf(`async function ${ten}(`);
  assert.ok(dau > 0, `phải có hàm ${ten}`);
  const cuoi = vatTu.indexOf("\n  async function ", dau + 10);
  return vatTu.slice(dau, cuoi > 0 ? cuoi : dau + 1500);
}

test("thêm vật tư thường: thành công thì xoá ô nguyên nhân, trong nhánh ok", () => {
  const t = than("them");
  const ok = t.indexOf("if (ok) {");
  assert.ok(ok > 0, "phải rẽ nhánh theo kết quả gửi");
  assert.match(t.slice(ok), /setLyDoBan\(""\)/);
  // Không xoá trước khi gửi (gửi hỏng thì mất chữ vừa gõ).
  assert.doesNotMatch(t.slice(0, t.indexOf('await gui("vat-tu-them"')), /setLyDoBan\(""\)/);
  assert.match(t, /ly_do_ban: lyDoBan\.trim\(\)/);
});

test("thêm qua ô quản lý duyệt: thành công thì cũng xoá ô nguyên nhân", () => {
  const t = than("xacNhanDuyet");
  const ok = t.indexOf("if (ok) {");
  assert.ok(ok > 0);
  assert.match(t.slice(ok), /setDuyet\(null\)[\s\S]*setLyDoBan\(""\)/);
  assert.doesNotMatch(t.slice(0, t.indexOf('await gui("vat-tu-them"')), /setLyDoBan\(""\)/);
});

test("ô nguyên nhân vẫn gửi kèm từng lần thêm và khoá nút khi dây bật mà chưa gõ", () => {
  assert.match(vatTu, /const thieuLyDo = goi\.bat_ly_do_ban && lyDoBan\.trim\(\)\.length < 5/);
  assert.match(vatTu, /\(thieuLyDo && !daCoDong\(m\.id\)\)/);
});
