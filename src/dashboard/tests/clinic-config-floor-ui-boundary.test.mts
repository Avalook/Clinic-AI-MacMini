import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path: string): string =>
  readFileSync(new URL(path, import.meta.url), "utf8");

const board = [
  read("../app/(dashboard)/settings/clinic-config/CoSoPhong.tsx"),
  read("../app/(dashboard)/settings/clinic-config/TangEditor.tsx"),
  read("../app/(dashboard)/settings/clinic-config/ViTriEditor.tsx"),
  read("../app/(dashboard)/settings/clinic-config/PhongForms.tsx"),
  read("../app/(dashboard)/settings/clinic-config/XacNhanXoa.tsx"),
].join("\n");
const route = read("../app/api/clinic-config/route.ts");

test("clinic config proxies the complete floor lifecycle", () => {
  assert.match(route, /"floor-create":\s*"\/api\/v1\/clinic-config\/floors"/);
  assert.match(route, /"floor-name":\s*"\/api\/v1\/clinic-config\/floor-name"/);
  assert.match(route, /"floor-active":\s*"\/api\/v1\/clinic-config\/floor-active"/);
  assert.match(route, /"floor-order":\s*"\/api\/v1\/clinic-config\/floor-order"/);
});

test("management can add, rename, reorder and softly remove floors on one screen", () => {
  for (const label of [
    "+ Thêm tầng",
    "Đổi tên tầng",
    "Đưa tầng lên",
    "Đưa tầng xuống",
    "Xoá tầng",
    "Khôi phục",
  ]) {
    assert.ok(board.includes(label), `thiếu thao tác ${label}`);
  }
  assert.match(board, /what[\s\S]*floor-create|goi\("POST",\s*"floor-create"/);
  assert.match(board, /goi\("PUT",\s*"floor-name"/);
  assert.match(board, /goi\("PUT",\s*"floor-active"/);
  assert.match(board, /goi\("PUT",\s*"floor-order"/);
  assert.match(board, /rooms\.filter\(\(room\) => room\.is_active\)/);
  assert.doesNotMatch(
    board,
    /floor\.is_active\s*&&\s*floor\.rooms\.length\s*>\s*0/,
    "phòng đã tắt không được khóa thao tác ngừng sử dụng tầng",
  );
});

test("rooms choose a floor id; Xoá hides them and Đã xoá restores them (04/11/2026)", () => {
  assert.match(board, /floor_id:/);
  assert.match(board, /nhan="Xoá phòng"/);
  assert.match(board, /room-active", \{ room_id: r\.room_id, is_active: true \}/);
  assert.match(board, /f\.rooms\.filter\(\(r\) => r\.is_active\)/);
  assert.doesNotMatch(board, />Tắt phòng</);
  assert.doesNotMatch(board, /window\.confirm/);
});

test("positions can be renamed and softly removed beside their room schedule", () => {
  assert.match(board, /thao_tac:\s*"vi-tri"/);
  assert.match(board, /nhan="Xoá vị trí"/);
  assert.match(board, /du_lieu: \{ is_active: true \}/);
  assert.match(board, /Lưu tên vị trí/);
});

test("room work groups and private services are temporarily hidden", () => {
  assert.doesNotMatch(board, /<ViecCuaPhong/);
  assert.doesNotMatch(board, /Phòng làm việc gì/);
  assert.doesNotMatch(board, /Dịch vụ riêng/);
});
