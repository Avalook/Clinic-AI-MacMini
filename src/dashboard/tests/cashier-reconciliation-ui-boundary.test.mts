import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const board = readFileSync(
  new URL("../app/(dashboard)/cashier/board/CashierBoard.tsx", import.meta.url),
  "utf8",
);

test("cashier reconciliation keeps the reference design's three working regions", () => {
  assert.match(board, /aria-label="Danh sách lượt khám"/);
  assert.match(board, /aria-label="Bảng đối soát chi tiết"/);
  assert.match(board, /aria-label="Chi tiết đối soát"/);
  // Cột giữa rộng lên từ 1.65fr: ở tỉ lệ cũ bảng đối soát rộng 740px nằm trong
  // khung 607px, nên cột "Đã thu" bị đẩy ra ngoài vùng nhìn thấy.
  assert.match(
    board,
    /xl:grid-cols-\[minmax\(200px,0\.68fr\)_minmax\(430px,1\.9fr\)_minmax\(240px,0\.9fr\)\]/,
  );
});

test("the visit list and reconciliation table expose the reference controls", () => {
  for (const label of [
    "Tìm tên, mã BN hoặc mã lượt khám",
    "Tất cả trạng thái",
    "Nguồn",
    "Hạng mục",
    "Trạng thái thực hiện",
    "Phải thu",
    "Đã thu",
    "Sai lệch",
  ]) {
    assert.match(board, new RegExp(label));
  }
});

test("the redesign keeps real charge facts and makes unsupported reconciliation unavailable", () => {
  for (const fact of [
    "charges.lines",
    "charges.subtotal",
    "charges.collected",
    "charges.outstanding",
    "charges.unpriced_lines",
    "l.unit_price",
  ]) {
    assert.match(board, new RegExp(fact.replace(".", "\\.")));
  }

  assert.match(board, /Chưa tính được thành tiền/);
  assert.match(board, /Giao việc xử lý/);
  assert.match(board, /Lưu ghi chú/);
  assert.match(board, /Xác nhận đã đối soát/);
  assert.match(board, /aria-pressed=\{currentLine === l\}/);
  assert.match(board, /aria-label=\{`Chọn hạng mục/);
  assert.match(
    board,
    /charges && charges\.unpriced_lines === 0 \? money\(charges\.subtotal\) : "—"/,
  );
  assert.match(
    board,
    /<button\s+type="button"\s+disabled\s+title="Chưa có nguồn sai lệch và biên bản đối soát để xác nhận"/,
  );
  assert.match(
    board,
    /<button\s+type="button"\s+disabled\s+title="Chưa có nguồn sai lệch và biên bản đối soát để hoàn tất quy trình"/,
  );
  assert.doesNotMatch(board, /commands\/\$\{command\}/);
  assert.doesNotMatch(board, /Sai lệch 1|Sai lệch 2|Nguồn ngoài \(Lab\)|EXT250514/);
});
