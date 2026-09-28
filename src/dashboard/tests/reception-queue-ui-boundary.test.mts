import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const board = readFileSync(
  new URL("../app/(dashboard)/reception/queue/QueueBoard.tsx", import.meta.url),
  "utf8",
);

/** Mã THỰC THI, đã bóc hết chú thích.
 *
 * Dùng cho mọi phép `doesNotMatch`. Chú thích được phép NHẮC tới thứ đã bỏ — đó
 * chính là chỗ giải thích vì sao nó bị bỏ — nhưng nhắc trong chú thích thì bài
 * kiểm lại báo vi phạm. Bản đầu của bài này đỏ đúng vì lý do ấy, và một bài
 * canh bắt nhầm là một bài canh sẽ bị người ta tắt đi.
 */
const maThucThi = board
  .replace(/\/\*[\s\S]*?\*\//g, "")
  .split("\n")
  .map((d) => d.split("//")[0])
  .join("\n");

// 27/09/2026 (đợt 3): danh sách tiếp đón làm lại theo bản mẫu Tuyền duyệt
// (`tiep-don.html`) — các bài kiểm của thiết kế cũ (ba vùng, không tab, panel
// một mốc giờ, "Mời <tên>") đã gỡ vì chính thiết kế ấy đã được thay.

test("danh sách tiếp đón: 3 tab, chia buổi, trạng thái do MÁY CHỦ tính", () => {
  for (const nhan of ["Tất cả", "Chưa đến", "Đã check-in"]) {
    assert.match(board, new RegExp(`nhan: "${nhan}"`));
  }
  // Chip trạng thái chỉ đọc chữ + loại máy chủ trả — màn không tự suy ra.
  assert.match(maThucThi, /d\.trang_thai\.nhan/);
  assert.match(maThucThi, /locTiepDon\(sapXepTiepDon\(goi\.buoi, huong\), tab, tim\)/);
  assert.doesNotMatch(maThucThi, /checked_in_at\s*\?\s*"Đã check-in"/);
});

test("sắp xếp Cũ/Mới nhất trước chỉ ĐẢO thứ tự máy chủ, không tự tính mốc giờ", () => {
  // 29/09/2026 (Tuyền): thứ tự theo giờ vào hàng thật là LUẬT → máy chủ. Màn
  // chỉ có công tắc xem; không `.sort(` và không đọc giờ check-in/giờ hẹn.
  assert.match(maThucThi, /Cũ nhất trước/);
  assert.match(maThucThi, /Mới nhất trước/);
  assert.doesNotMatch(maThucThi, /\.sort\(/);
  assert.doesNotMatch(maThucThi, /checked_in_at|slot_start/);
});

test("thêm khách xong về màn Tiếp đón — cửa hỏi theo lego của trang đích", () => {
  // 29/09/2026 (Tuyền): lễ tân thêm khách mới xong thì nhảy về Tiếp đón khách.
  // Trang quyết bằng `moDuocMan("/reception/queue")` (lego), không theo vai.
  const trang = readFileSync(
    new URL("../app/(dashboard)/patients/new/page.tsx", import.meta.url),
    "utf8",
  );
  const form = readFileSync(
    new URL("../app/(dashboard)/patients/new/NewPatientForm.tsx", import.meta.url),
    "utf8",
  );
  assert.match(trang, /moDuocMan\("\/reception\/queue"\)/);
  assert.match(trang, /veTiepDon=\{veTiepDon\}/);
  assert.match(form, /if \(veTiepDon\) \{\s*router\.push\("\/reception\/queue"\);/);
});

test("không bịa dữ liệu vận hành", () => {
  // Phần giá trị nhất của bài kiểm cũ, giữ nguyên: màn hình không được vẽ ra
  // tên người, số quầy hay số thẻ BHYT mà hệ thống chưa hề có.
  assert.doesNotMatch(maThucThi, /Trần Ngọc Mai|A021|Quầy 0[1-9]|BHYT:\s*\d/);
});
