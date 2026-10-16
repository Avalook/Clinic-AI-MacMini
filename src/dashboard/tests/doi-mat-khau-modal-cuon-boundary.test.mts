import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// Đổi mật khẩu cá nhân (16/10/2026): hộp căn giữa mà không cuộn được thì ở màn
// thấp (laptop phóng to, điện thoại ngang, khung xem trước ~380px) ô "Mật khẩu
// hiện tại" nằm ngoài màn hình → nút Lưu xám mãi (nút cần đủ ba ô) → "không đổi
// được". Lớp phủ phải cuộn được; hộp vẫn căn giữa khi màn đủ cao.
const src = readFileSync(
  new URL("../app/(dashboard)/DoiMatKhauModal.tsx", import.meta.url),
  "utf8",
);

test("lớp phủ hộp đổi mật khẩu cuộn được theo chiều dọc", () => {
  const phu = src.match(/className="(fixed inset-0[^"]*)"/);
  assert.ok(phu, "phải có lớp phủ fixed inset-0");
  assert.ok(phu[1].includes("overflow-y-auto"), "lớp phủ phải overflow-y-auto");
  assert.ok(
    !/\bitems-center\b/.test(phu[1]),
    "căn giữa đặt ở lớp trong (min-h-full), không đặt ở lớp phủ — lớp phủ căn giữa sẽ cắt phần trên",
  );
});

test("hộp vẫn căn giữa khi màn cao (lớp trong min-h-full)", () => {
  assert.ok(
    /className="flex min-h-full items-center justify-center"/.test(src),
    "lớp trong phải là flex min-h-full items-center justify-center",
  );
});

test("nút Lưu vẫn đòi đủ ba ô (không nới luật)", () => {
  assert.ok(
    /disabled=\{busy \|\| !oldPassword \|\| !newPassword \|\| !confirmPassword\}/.test(
      src,
    ),
  );
});
