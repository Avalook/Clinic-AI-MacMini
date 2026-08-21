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

// ── Đường proxy phải giữ nguyên mã trạng thái ──────────────────────────────
//
// `fetchFromBackend` trả `null` cho MỌI lỗi, nên route nào dùng nó rồi tự chế
// mã trạng thái sẽ biến 403 "không đủ quyền" thành 503 "máy chủ hỏng". Đo tải
// 100 người ngày 22/08/2026 bắt được đúng ca này ở `/api/ca-lam-viec`:
// 240/240 lượt của Lễ tân và CSKH nhận 503. Chính `backend-proxy.ts` đã cảnh
// báo bẫy này bằng một đoạn chú thích dài — mà vẫn vấp.
//
// Luật: route nào PHỤ THUỘC QUYỀN (backend có thể trả 403) thì dùng
// `proxyJsonToBackend`, vì nó chuyển tiếp nguyên mã và câu lỗi.

const routeCaLamViec = readFileSync(
  new URL("../app/api/ca-lam-viec/route.ts", import.meta.url),
  "utf8",
);

test("route giờ ca giữ nguyên mã trạng thái của backend", () => {
  // Soi LỜI GỌI (có ngoặc mở) và dòng IMPORT, không soi chữ: chú thích có
  // quyền nhắc tên hàm cũ khi kể lại vì sao bỏ nó. Đây là lần thứ ba trong
  // ngày cùng một cái bẫy viết test — grep chữ thì chú thích cũng dính.
  assert.doesNotMatch(
    routeCaLamViec,
    /fetchFromBackend\(/,
    "gọi fetchFromBackend là nuốt mã 403 thành 503 — dùng proxyJsonToBackend",
  );
  assert.doesNotMatch(
    routeCaLamViec,
    /^import .*fetchFromBackend/m,
    "còn import fetchFromBackend nghĩa là còn đường quay lại lối tắt",
  );
  assert.match(routeCaLamViec, /proxyJsonToBackend\("GET"/);
  assert.match(routeCaLamViec, /proxyJsonToBackend\("PATCH"/);
});
