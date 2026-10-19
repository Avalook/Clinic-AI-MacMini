import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const doc = (path: string) =>
  readFileSync(new URL(`../${path}`, import.meta.url), "utf8");

test("Lịch làm việc ẩn dải cảnh báo dự kiến và mô tả phụ", () => {
  const page = doc("app/(dashboard)/schedule/page.tsx");
  const apply = doc("app/(dashboard)/schedule/ApDungTuan.tsx");

  assert.doesNotMatch(
    page,
    /<p className="mt-1 text-sm text-ink-muted">\s*Lịch trực do trưởng ca xếp/,
  );
  assert.doesNotMatch(page, /Form y hệt file Excel/);
  assert.doesNotMatch(apply, /Lịch dự kiến — chưa áp dụng/);
  assert.match(apply, /Áp dụng tuần/);
  assert.match(
    apply,
    /return \(\s*<div className="flex flex-wrap items-center gap-2">\s*\{laQuanLy && \(\s*<Button[\s\S]*?Áp dụng tuần/,
  );
});

test("Nhật ký thao tác lấy trọn dữ liệu ngày, không cắt cứng 200 sự kiện", () => {
  const page = doc("app/(dashboard)/audit-log/page.tsx");
  const board = doc("app/(dashboard)/audit-log/AuditLogBoard.tsx");
  const service = readFileSync(
    new URL("../../clinicai/services/audit_log_service.py", import.meta.url),
    "utf8",
  );

  assert.doesNotMatch(page, /audit\/events\?limit=200/);
  assert.match(page, /"\/api\/v1\/audit\/events"/);
  assert.match(board, /useState<AuditTab>\("all"\)/);
  assert.match(board, /events\[0\]/);
  assert.match(board, /filtered\.map/);
  assert.doesNotMatch(board, /filtered\.slice/);
  assert.match(service, /occurred_at >= \$2/);
  assert.match(service, /occurred_at < \$3/);
  assert.doesNotMatch(service, /\b(?:LIMIT|OFFSET)\b/i);
  assert.match(service, /ORDER BY occurred_at DESC/);
});
