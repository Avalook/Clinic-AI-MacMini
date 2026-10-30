// [Không đo] sinh hiệu + lý do (30/10/2026). Màn chỉ vẽ: chip lý do và câu
// "Không đo · <lý do>" đến từ MÁY CHỦ; lệnh đi qua proxy `khong-do`.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path: string): string => readFileSync(new URL(path, import.meta.url), "utf8");

const bang = read("../app/(dashboard)/do-sinh-hieu/BangDoSinhHieu.tsx");
const proxy = read("../app/api/luot-kham/route.ts");
const theKhach = read("../app/(dashboard)/_lam-viec/phieu-kham/TheKhach.tsx");
const inPhieu = read("../app/print/phieu-kham/[visitId]/InPhieuKham.tsx");
const banKham = read("../app/(dashboard)/ban-kham/BanKham.tsx");
const live = read("../app/(dashboard)/RealtimeRefresher.tsx");

test("nút Không đo cạnh Đo xong, chip lý do lấy từ máy chủ, gửi lệnh khong-do", () => {
  assert.match(bang, />\s*Không đo\s*</);
  assert.match(bang, /ly_do_khong_do/);
  assert.match(bang, /thao_tac: "khong-do"/);
  // Danh sách chữ chip KHÔNG viết cứng ở màn.
  assert.doesNotMatch(bang, /"Trẻ nhỏ"|"Khách từ chối"|"Đã đo nơi khác"/);
  assert.match(proxy, /"khong-do": \(id\) => `\/api\/v1\/luot-kham\/visits\/\$\{id\}\/vitals\/khong-do`/);
});

test("khách Không đo không kẹt hàng chờ đo; đo sau vẫn mở được", () => {
  assert.match(bang, /\.find\(\(l\) => !l\.sinh_hieu && !l\.khong_do\)/);
  assert.match(bang, /daDo: ds\.filter\(xongBuoc\)/);
});

test("bàn khám / phiếu khám / phiếu in hiện câu Không đo của máy chủ", () => {
  assert.match(theKhach, /sinh_hieu_khong_do/);
  assert.match(inPhieu, /sinh_hieu_khong_do/);
  assert.match(banKham, /khong_do\?\.nhan/);
  assert.match(live, /"sinh_hieu_khong_do"/);
});
