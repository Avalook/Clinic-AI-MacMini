import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const board = readFileSync(
  new URL("../app/(dashboard)/doctor/board/DoctorBoard.tsx", import.meta.url),
  "utf8",
);
const page = readFileSync(
  new URL("../app/(dashboard)/doctor/board/page.tsx", import.meta.url),
  "utf8",
);

test("the doctor board keeps the reference design's three working regions", () => {
  assert.match(board, /aria-label="Hàng đợi đang mở"/);
  assert.match(board, /aria-label="Hồ sơ khám bệnh"/);
  assert.match(board, /aria-label="Việc còn thiếu và điều phối"/);
  // Cột trái rộng lên từ 210px/0.78fr: ở tỉ lệ cũ tên bệnh nhân và tên bước bị
  // cắt thành "Hoàng Phư…" / "Tạ…" trên màn 1600px.
  assert.match(
    board,
    /xl:grid-cols-\[minmax\(250px,1\.05fr\)_minmax\(420px,1\.7fr\)_minmax\(230px,0\.72fr\)\]/,
  );
});

test("the worklist and clinical workspace expose the reference navigation", () => {
  for (const label of [
    "Tìm bệnh nhân hoặc mã hồ sơ",
    "Chờ khám",
    "Đang khám",
    "Quay lại đọc kết quả",
    "Khám bác sĩ",
    "Chỉ định",
    "Kết quả",
    "Đơn thuốc",
    "Thuốc & thanh toán",
  ]) {
    assert.match(board, new RegExp(label));
  }
});

test("the redesign preserves real workflow actions and the shared status vocabulary", () => {
  assert.match(board, /STATUS_PRESENTATION/);
  assert.match(board, /resolveStatus/);
  assert.match(board, /WorkItemActions/);
  assert.match(board, /\/api\/work-items\/\$\{item\.id\}\/commands\/\$\{command\}/);
  assert.match(board, /Mở màn chỉ định dịch vụ/);
  assert.match(board, /visibleItems\.find\(\(item\) => item\.id === selectedId\) \?\?/);
  assert.match(board, /<QueuePanel\s+items=\{visibleItems\}/);
  assert.doesNotMatch(board, /getSupabaseService|SUPABASE_SERVICE_ROLE_KEY/);
});

test("clinical cards tell the truth when their source data is unavailable", () => {
  for (const label of [
    "Màn này chưa kết nối nguồn dữ liệu sinh hiệu",
    "Màn này chưa kết nối nội dung khám lâm sàng",
    "Màn này chưa kết nối chỉ định hoặc kết quả để hiển thị",
    "Màn này chưa kết nối dữ liệu đơn thuốc",
    "Màn này chưa kết nối dữ liệu thanh toán",
  ]) {
    assert.match(board, new RegExp(label));
  }

  assert.doesNotMatch(board, /110\/70|36\.6|52\.0|Viêm âm đạo|Clotrimazole/);
  assert.match(page, /Danh sách khám bệnh đang mở/);
  assert.doesNotMatch(page + board, /Tổng: \{visible\.length\} bệnh nhân|Lịch hôm nay/);
});
