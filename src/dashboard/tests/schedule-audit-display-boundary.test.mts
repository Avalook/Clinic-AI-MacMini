import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const doc = (path: string) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");

test("Lịch làm việc ẩn dải cảnh báo dự kiến và dòng mô tả phụ", () => {
  const page = doc("app/(dashboard)/schedule/page.tsx");
  const apply = doc("app/(dashboard)/schedule/ApDungTuan.tsx");

  assert.doesNotMatch(
    page,
    /<p className="mt-1 text-sm text-ink-muted">\s*Lịch trực do trưởng ca xếp/,
  );
  assert.match(apply, /if \(!laQuanLy && !daApDung && !vuaApDung\) return null/);
});

test("Nhật ký thao tác lấy trọn dữ liệu ngày, không cắt cứng 200 sự kiện", () => {
  const page = doc("app/(dashboard)/audit-log/page.tsx");
  const service = readFileSync(
    new URL("../../clinicai/services/audit_log_service.py", import.meta.url),
    "utf8",
  );

  assert.doesNotMatch(page, /audit\/events\?limit=200/);
  assert.match(service, /occurred_at >= \$2/);
  assert.match(service, /occurred_at < \$3/);
  assert.doesNotMatch(service, /LIMIT \$2/);
});
