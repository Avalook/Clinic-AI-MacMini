import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

// VAI LÀM VIỆC HÔM NAY (Tuyền duyệt 16/09/2026: "làm sao cho không bị lỗi nữa").
//
// Lỗi gốc: 38 trang/route và trang chủ đọc VAI TÀI KHOẢN, nên Phùng Thị Minh Thư
// (tài khoản Điều dưỡng, hôm nay đứng Lễ tân) nhận trang chủ "Điền sinh hiệu",
// bị 403 ở thu ngân, bị đá khỏi Tạo bệnh nhân. Mọi quyết định giờ đi qua MỘT
// nguồn: `getVaiHomNay` / `getVaiChinh` / `vaiLamViec` trong lib/clinic-session.ts.
// Bài này cấm đường tắt đọc vai tài khoản sống lại ở chỗ khác.

const goc = new URL("..", import.meta.url).pathname;

function tatCaTep(thuMuc: string): string[] {
  const ra: string[] = [];
  for (const ten of readdirSync(thuMuc)) {
    if (ten === "node_modules" || ten.startsWith(".")) continue;
    const p = join(thuMuc, ten);
    if (statSync(p).isDirectory()) ra.push(...tatCaTep(p));
    else if (/\.(ts|tsx)$/.test(ten) && !/\.test\.m?ts$/.test(ten)) ra.push(p);
  }
  return ra;
}

test("không màn nào đọc vai TÀI KHOẢN trực tiếp — chỉ qua vai hôm nay", () => {
  const viPham = [...tatCaTep(join(goc, "app")), ...tatCaTep(join(goc, "lib"))]
    .filter((p) => !p.endsWith("lib/clinic-session.ts"))
    .filter((p) => /\bgetClinicRole\s*\(/.test(readFileSync(p, "utf8")))
    .map((p) => p.slice(goc.length));
  assert.deepEqual(viPham, [], `đọc vai tài khoản trực tiếp: ${viPham.join(", ")}`);
});

test("vai theo vị trí đứng TRƯỚC vai tài khoản — việc hôm nay quyết định màn hình", () => {
  const src = readFileSync(join(goc, "lib/clinic-session.ts"), "utf8");
  // Vai vị trí (máy chủ đã xếp Lễ tân → Điều dưỡng → Trưởng ca) đứng trước; vai
  // tài khoản nối cuối nếu chưa có (17/09/2026).
  assert.match(src, /return theo\.includes\(goc\) \? theo : \[\.\.\.theo, goc\];/);
  assert.match(src, /export async function getVaiChinh\(/);
});

test("cửa vào trang xét MỌI vai hôm nay, không chỉ một vai", () => {
  // Màn NGOÀI lego vẫn xét mọi vai hôm nay; màn thuộc lego hỏi lego (27/09).
  const src = readFileSync(join(goc, "lib/clinic-session.ts"), "utf8");
  const i = src.indexOf("export async function moDuocMan");
  assert.match(src.slice(i, i + 300), /getVaiHomNay\(\), getQuyenCuaToi\(\)/);
  const roles = readFileSync(join(goc, "lib/roles.ts"), "utf8");
  const j = roles.indexOf("export function vaoDuocMan");
  assert.match(roles.slice(j, j + 600), /vai\.some\(\(r\) => canSeeNav\(r, href\)\)/);
});

test("trang chủ và bảng việc chọn màn theo VAI CHÍNH hôm nay", () => {
  for (const trang of ["app/(dashboard)/home/page.tsx", "app/(dashboard)/tasks/page.tsx"]) {
    assert.match(readFileSync(join(goc, trang), "utf8"), /await getVaiChinh\(\)/, trang);
  }
});
