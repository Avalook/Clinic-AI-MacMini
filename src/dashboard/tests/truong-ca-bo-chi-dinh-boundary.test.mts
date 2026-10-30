// Trưởng ca bỏ chỉ định ngay trên màn điều phối (30/10/2026).
// Nút chỉ vẽ theo cờ MÁY CHỦ (`bo_duoc`, `hoan_tac_bo_id`), gửi đúng lệnh của
// phiếu khám (`huy-chi-dinh`) và lệnh hoàn tác của sổ (`hoan-tac-bo-chi-dinh`).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path: string): string => readFileSync(new URL(path, import.meta.url), "utf8");

const chiDinh = read("../app/(dashboard)/truong-ca/ChiDinhCuaBacSi.tsx");

test("nút Bỏ chỉ định hiện theo cờ máy chủ, gửi lệnh huy-chi-dinh", () => {
  assert.match(chiDinh, /x\.bo_duoc \?/);
  assert.match(chiDinh, /lenhHoanTac\("huy-chi-dinh", x\.id\)/);
  assert.match(chiDinh, /nhan="Bỏ chỉ định"/);
  // Cùng hộp hỏi với phiếu khám — không window.confirm.
  assert.match(chiDinh, /<NutHoanTac/);
  assert.doesNotMatch(chiDinh, /window\.confirm/);
});

test("bỏ rồi có Hoàn tác bằng dòng sổ máy chủ trả", () => {
  assert.match(chiDinh, /x\.hoan_tac_bo_id \?/);
  assert.match(chiDinh, /lenhHoanTac\("hoan-tac-bo-chi-dinh", x\.hoan_tac_bo_id\)/);
});

test("hộp hỏi lại của Bỏ chỉ định xác nhận bằng chữ 'Bỏ chỉ định', không 'Hoàn tác'", () => {
  // Bấm thử 30/10: nút ngoài "Bỏ chỉ định" mà nút trong hộp ghi "Hoàn tác" —
  // người bấm tưởng là nút huỷ thao tác.
  assert.match(chiDinh, /nhanXacNhan="Bỏ chỉ định"/);
  const nut = read("../components/ui/NutHoanTac.tsx");
  assert.match(nut, /nhanXacNhan=\{nhanXacNhan\}/);
  assert.doesNotMatch(nut, /nhanXacNhan="Hoàn tác"\n/);
});

test("màn không tự suy luật bỏ được từ trạng thái", () => {
  assert.doesNotMatch(chiDinh, /bo_duoc\s*=\s*.*exec_status/);
});
