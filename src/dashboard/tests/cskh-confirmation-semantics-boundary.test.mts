import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const ROOT = new URL("../", import.meta.url);
const read = (path: string) => readFileSync(new URL(path, ROOT), "utf8");

const motCham = read("app/(dashboard)/customers/mot-cham.ts");
const vungLamViec = read("app/(dashboard)/customers/VungLamViecKhach.tsx");
const lichSu = read("app/(dashboard)/customers/LichSuCacLanKham.tsx");
const lichTrung = read("app/(dashboard)/customers/LichTrungCuaKhach.tsx");
const statusBadge = read("app/(dashboard)/StatusBadge.tsx");
const cskhTasks = read("app/(dashboard)/cskh-tasks/CskhTasksView.tsx");

function khoiMotCham(ma: string): string {
  const batDau = motCham.indexOf(`  ${ma}: {`);
  assert.ok(batDau >= 0, `không tìm thấy cấu hình một-chạm ${ma}`);
  const ketThuc = motCham.indexOf("\n  },", batDau);
  assert.ok(ketThuc > batDau, `không tìm thấy cuối cấu hình ${ma}`);
  return motCham.slice(batDau, ketThuc);
}

test("hai cuộc gọi trước khám ghi rõ khách đã xác nhận", () => {
  for (const ma of ["CHO_XAC_NHAN", "NHAC_HEN_MAI"]) {
    assert.match(
      khoiMotCham(ma),
      /khachXacNhan:\s*true/,
      `${ma} đóng việc bằng nhãn đã xác nhận nhưng chưa ghi khach_xac_nhan=true`,
    );
  }
});

test("payload một-chạm chuyển cờ xác nhận sang API", () => {
  assert.match(
    vungLamViec,
    /khach_xac_nhan:\s*v\.khachXacNhan\s*\?\?\s*null/,
    "payload /api/cskh/tuong-tac chưa chuyển khachXacNhan từ MOT_CHAM",
  );
});

test("màn CSKH gọi CONFIRMED là Đã đặt lịch, không phải đã gọi xác nhận", () => {
  for (const [ten, source] of [
    ["Lịch sử các lần khám", lichSu],
    ["Lịch trùng của khách", lichTrung],
    ["Nhãn trạng thái dùng chung", statusBadge],
    ["Danh sách việc CSKH", cskhTasks],
  ] as const) {
    assert.match(source, /\bCONFIRMED:\s*"Đã đặt lịch"/, `${ten} dùng sai nhãn CONFIRMED`);
    assert.doesNotMatch(
      source,
      /\bCONFIRMED:\s*"Đã xác nhận"/,
      `${ten} đang đánh đồng lịch đã đặt với khách đã xác nhận sẽ đến`,
    );
  }
});
