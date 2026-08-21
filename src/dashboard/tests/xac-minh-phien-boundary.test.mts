// Xác minh phiên MỘT lần cho mỗi lượt dựng trang — đừng để tuột lại.
//
// Đo trên staging 21/08/2026 (bật log SQL cho đúng một request): một lần mở
// /home chạy lại chuỗi users/sessions/mfa của gotrue nhiều lần cho CÙNG một
// người, vì mỗi nơi gọi getSupabaseServer tự dựng client riêng và
// fetchFromBackend nào cũng tự getUser() lại. Hai chỗ dưới đây gói bằng
// React cache() — một client, một lần xác minh cho cả lượt render; route
// handler không có kho theo-request thì cache() tự thành gọi thẳng nên mỗi
// request rời vẫn tự xác minh như cũ.
//
// Bài kiểm đọc NGUỒN vì hành vi cache() cần kho theo-request của Next mà
// node --test không dựng được; đổi cách gói thì sửa bài kiểm này cùng lúc.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const supabaseServer = readFileSync(
  new URL("../lib/supabase-server.ts", import.meta.url),
  "utf8",
);
const backendProxy = readFileSync(
  new URL("../lib/backend-proxy.ts", import.meta.url),
  "utf8",
);

test("getSupabaseServer gói trong cache() — một client mỗi lượt render", () => {
  assert.match(
    supabaseServer,
    /export const getSupabaseServer = cache\(/,
    "bỏ cache() là mỗi server component tự dựng client + tự xác minh lại",
  );
});

test("refreshQuietly gói trong cache() — một lần getUser mỗi lượt render", () => {
  assert.match(
    backendProxy,
    /const refreshQuietly = cache\(/,
    "bỏ cache() là mỗi fetchFromBackend một vòng gotrue users/sessions/mfa",
  );
});

test("cache() lấy từ react — không phải bản tự chế", () => {
  for (const [ten, nguon] of [
    ["supabase-server", supabaseServer],
    ["backend-proxy", backendProxy],
  ] as const) {
    assert.match(
      nguon,
      /import \{ cache \} from "react"/,
      `${ten}: cache() phải là của React để theo đúng vòng đời request`,
    );
  }
});
