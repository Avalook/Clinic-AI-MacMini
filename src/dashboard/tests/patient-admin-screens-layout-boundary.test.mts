import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const DASHBOARD = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function readDashboardFile(relativePath: string): string {
  return readFileSync(path.join(DASHBOARD, relativePath), "utf8");
}

function countMatches(source: string, pattern: RegExp): number {
  return [...source.matchAll(pattern)].length;
}

test("patient list controls share one top overview row", () => {
  const source = readDashboardFile(
    "app/(dashboard)/patient-list/PatientListView.tsx",
  );
  const overviewTools = source.match(
    /const overviewTools = \([\s\S]*?\n  \);/,
  )?.[0];
  const directory = source.match(/const directory = \([\s\S]*?\n  \);/)?.[0];

  assert.ok(overviewTools, "a shared overview toolbar should be defined");
  assert.ok(directory, "the selected-patient directory should be defined");
  assert.match(overviewTools, /aria-label="Lọc danh sách bệnh nhân"/);
  assert.match(overviewTools, /nutChieuXep/);
  assert.equal(
    countMatches(source, /aria-label="Tìm tên, mã BN hoặc SĐT"/g),
    1,
    "search should be declared once and reused across views",
  );
  assert.equal(
    countMatches(source, /aria-label="Lọc danh sách bệnh nhân"/g),
    1,
    "filter chips should be declared once and reused across views",
  );
  assert.doesNotMatch(directory, /Tìm tên, mã BN|Lọc danh sách bệnh nhân|nutChieuXep/);
  assert.equal(
    countMatches(source, /\{overviewTools\}/g),
    4,
    "the overview row should stay visible in each patient-list view",
  );
});

test("new patient flow switch has no duplicate card header", () => {
  const source = readDashboardFile(
    "app/(dashboard)/patients/new/page.tsx",
  );

  assert.match(source, /<nav aria-label="Chọn luồng tạo hồ sơ"/);
  assert.doesNotMatch(source, /rounded-card border border-line bg-surface px-4 py-3 shadow-card/);
  assert.match(source, /Nhập thông tin khách hàng mới/);
  assert.match(source, /Tạo bệnh nhân mới/);
  assert.match(source, /\n\s*nhung\n/);
});

test("permission screen omits the highlighted instruction line", () => {
  const source = readDashboardFile(
    "app/(dashboard)/phan-quyen/BangPhanQuyen.tsx",
  );

  assert.doesNotMatch(
    source,
    /Tick kỹ năng người này làm — tick là mở đúng các màn, phòng ghi bên cạnh\./,
  );
  assert.match(source, /<KyNangCuaNguoi/);
});

test("settings không còn khung Chế độ phòng khám (29/10/2026: chỉ chạy đầy đủ)", () => {
  const source = readDashboardFile("app/(dashboard)/settings/page.tsx");
  assert.doesNotMatch(source, /<FeatureModeCard/);
  assert.match(source, /<BookingPolicyCard/);
});
