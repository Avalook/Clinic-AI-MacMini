import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const board = readFileSync(
  new URL("../app/(dashboard)/reception/queue/QueueBoard.tsx", import.meta.url),
  "utf8",
);

test("the reception queue keeps the reference design's three working regions", () => {
  assert.match(board, /aria-label="Danh sách hàng đợi"/);
  assert.match(board, /aria-label="Thông tin người bệnh"/);
  assert.match(board, /aria-label="Điều phối tại quầy"/);
  assert.match(
    board,
    /xl:grid-cols-\[minmax\(280px,0\.9fr\)_minmax\(380px,1\.25fr\)_minmax\(240px,0\.8fr\)\]/,
  );
  assert.doesNotMatch(board, /Chưa có: điều phối quầy/);
});

test("the queue list provides the documented navigation and finding controls", () => {
  for (const label of [
    "Tất cả",
    "Ưu tiên",
    "Cần xác minh",
    "Tìm tên, mã BN hoặc số thứ tự",
    "Bộ lọc",
    "Sắp xếp",
  ]) {
    assert.match(board, new RegExp(label));
  }
});

test("the patient detail preserves all five reception sub-steps", () => {
  for (const label of [
    "Vào hàng đợi",
    "Đã gán quầy",
    "Gọi bệnh nhân",
    "Xác nhận có mặt",
    "Hoàn tất tiếp nhận",
  ]) {
    assert.match(board, new RegExp(label));
  }
});

test("the documented action set is visible without inventing operational data", () => {
  for (const label of [
    "Gọi số",
    "Xác nhận có mặt & hoàn tất",
    "Đánh dấu vắng mặt",
    "Tạm giữ",
    "Xử lý ngoại lệ",
  ]) {
    assert.match(board, new RegExp(label));
  }
  assert.match(board, /required/);
  assert.doesNotMatch(board, /issue\("skip"/);
  assert.match(board, /tab === "verify" && item\.node_code === "LUOTKHAM-02"/);
  assert.match(board, /title="Backend chưa có lệnh gọi số và mốc thời gian gọi"/);
  assert.match(board, /"Bắt đầu xử lý"/);
  assert.match(board, /filtered\.find\(\(item\) => item\.id === selectedId\) \?\?/);
  assert.doesNotMatch(board, /Trần Ngọc Mai|A021|Quầy 0[1-9]|BHYT:\s*\d/);
});
