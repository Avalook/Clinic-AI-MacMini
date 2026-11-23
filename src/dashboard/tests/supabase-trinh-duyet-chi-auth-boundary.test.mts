// TRÌNH DUYỆT CHỈ ĐƯỢC GỌI `supabase.auth.*` (23/11/2026, bảo mật).
//
// Caddy đã ĐÓNG `/rest/v1` và `/realtime/v1` từ Internet (caddy/Caddyfile, test
// src/tests/test_caddy_dong_rest_v1.py): để mở là ai đăng nhập được — kể cả Đối
// tác, TV phòng chờ — đọc thẳng ~110 bảng. Đóng được vì trình duyệt chỉ dùng
// supabase-js cho đăng nhập/mật khẩu.
//
// Bài này canh nửa còn lại: một màn mới lỡ gọi `supabase.from(...)` từ trình
// duyệt thì chạy đúng ở dev (dev gọi thẳng gateway, không qua Caddy) nhưng trên
// prod nhận 403 im lặng — màn rỗng. Đọc dữ liệu thì đi FastAPI qua route Next.

import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import test from "node:test";

const GOC = new URL("../", import.meta.url);

function moiFileNguon(thuMuc: URL, ra: string[] = []): string[] {
  for (const ten of readdirSync(thuMuc)) {
    if (ten === "node_modules" || ten === ".next" || ten.startsWith(".")) continue;
    const duong = new URL(ten, thuMuc);
    if (statSync(duong).isDirectory()) {
      moiFileNguon(new URL(`${ten}/`, thuMuc), ra);
    } else if (/\.(ts|tsx|mts)$/.test(ten)) {
      ra.push(duong.pathname);
    }
  }
  return ra;
}

const boChuThich = (ma: string) =>
  ma.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");

// Bỏ tests/: chính các bài canh chứa mẫu cần tìm.
const NGUON = moiFileNguon(GOC)
  .map((p) => ({
    duong: p.slice(GOC.pathname.length),
    ma: boChuThich(readFileSync(p, "utf8")),
  }))
  .filter((f) => !f.duong.startsWith("tests/"));

// Ba chỗ hôm nay dùng supabase phía trình duyệt — đều chỉ cho mật khẩu. Thêm
// chỗ mới thì phải sửa danh sách này có chủ ý (và vẫn chỉ được `.auth.*`).
const DUOC_DUNG_TRINH_DUYET = [
  "app/(auth)/forgot-password/ForgotPasswordForm.tsx",
  "app/(auth)/reset-password/ResetPasswordForm.tsx",
  "app/(dashboard)/DoiMatKhauModal.tsx",
];

test("chỉ lib/supabase-browser.ts dựng client trình duyệt", () => {
  const dung = NGUON.filter((f) => /createBrowserClient\(/.test(f.ma)).map(
    (f) => f.duong,
  );
  assert.deepEqual(dung, ["lib/supabase-browser.ts"]);
});

test("file 'use client' không import thẳng thư viện supabase", () => {
  const lo = NGUON.filter(
    (f) => /^\s*["']use client["']/m.test(f.ma) && /from ["']@supabase\//.test(f.ma),
  ).map((f) => f.duong);
  assert.deepEqual(lo, [], "client trình duyệt chỉ lấy qua getSupabaseBrowser()");
});

test("chỉ ba màn mật khẩu dùng getSupabaseBrowser()", () => {
  const dung = NGUON.filter(
    (f) =>
      f.duong !== "lib/supabase-browser.ts" && /getSupabaseBrowser\b/.test(f.ma),
  )
    .map((f) => f.duong)
    .sort();
  assert.deepEqual(dung, DUOC_DUNG_TRINH_DUYET);
});

test("client trình duyệt chỉ gọi .auth.*", () => {
  for (const duong of DUOC_DUNG_TRINH_DUYET) {
    const ma = NGUON.find((f) => f.duong === duong)!.ma;
    // Mọi biến nhận getSupabaseBrowser() — tên nào cũng bắt.
    const bien = [...ma.matchAll(/(\w+)\s*=\s*getSupabaseBrowser\(\)/g)].map(
      (m) => m[1],
    );
    assert.ok(bien.length > 0, `${duong}: không thấy biến nhận getSupabaseBrowser()`);
    for (const b of bien) {
      const goi = [...ma.matchAll(new RegExp(`\\b${b}\\s*\\.\\s*(\\w+)`, "g"))].map(
        (m) => m[1],
      );
      const sai = goi.filter((g) => g !== "auth");
      assert.deepEqual(
        sai,
        [],
        `${duong}: ${b}.${sai[0]} — /rest/v1 và /realtime/v1 đã đóng ở Caddy, đọc dữ liệu qua FastAPI`,
      );
    }
  }
});
