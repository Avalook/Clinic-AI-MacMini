import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// 17/10/2026: `supabase.auth.signOut()` không tham số mặc định là scope "global" —
// thu hồi MỌI phiên của tài khoản, đá cả những máy khác đang dùng cùng nick.
// Phòng khám dùng chung tài khoản trên nhiều máy, nên đăng xuất ở luồng đăng nhập
// phải là "local". Hai chỗ cố ý KHÁC: ResetPasswordForm (đặt lại mật khẩu → đá tất
// cả) và DoiMatKhauModal (`scope: "others"`).

const GOC = new URL("../", import.meta.url);
const LOGIN = "app/(auth)/login/actions.ts";

test("login/actions.ts: mọi signOut đều chỉ thu hồi phiên máy này", () => {
  const src = readFileSync(new URL(LOGIN, GOC), "utf8");
  const calls = [...src.matchAll(/auth\.signOut\(([^)]*)\)/g)];
  assert.ok(calls.length >= 4, `mong thấy ≥4 lời gọi signOut, thấy ${calls.length}`);
  for (const m of calls) {
    assert.match(
      m[1],
      /scope:\s*"local"/,
      `signOut(${m[1]}) phải có scope: "local" — mặc định là global, đá mọi máy khác`,
    );
  }
});

test("hai chỗ cố ý vẫn đúng ý: đặt lại mật khẩu đá tất cả, đổi mật khẩu đá máy khác", () => {
  const reset = readFileSync(
    new URL("app/(auth)/reset-password/ResetPasswordForm.tsx", GOC),
    "utf8",
  );
  const doi = readFileSync(new URL("app/(dashboard)/DoiMatKhauModal.tsx", GOC), "utf8");
  assert.match(reset, /auth\.signOut\(\s*\)/);
  assert.match(doi, /auth\.signOut\(\{\s*scope:\s*"others"\s*\}\)/);
});
