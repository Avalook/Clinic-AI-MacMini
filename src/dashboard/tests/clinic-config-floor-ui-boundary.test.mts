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
    "Ngừng sử dụng tầng",
    "Dùng lại tầng",
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

test("rooms choose a floor id and use explicit soft-removal wording", () => {
  assert.match(board, /floor_id:/);
  assert.match(board, /Ngừng sử dụng phòng/);
  assert.match(board, /Dùng lại phòng/);
  assert.doesNotMatch(board, />Tắt phòng</);
});

test("positions can be renamed and softly removed beside their room schedule", () => {
  assert.match(board, /thao_tac:\s*"vi-tri"/);
  assert.match(board, /is_active:\s*!viTri\.is_active/);
  assert.match(board, /Ngừng sử dụng vị trí/);
  assert.match(board, /Dùng lại vị trí/);
  assert.match(board, /Lưu tên vị trí/);
});

test("room work groups and private services are temporarily hidden", () => {
  assert.doesNotMatch(board, /<ViecCuaPhong/);
  assert.doesNotMatch(board, /Phòng làm việc gì/);
  assert.doesNotMatch(board, /Dịch vụ riêng/);
});
