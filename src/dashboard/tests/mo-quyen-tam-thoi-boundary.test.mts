import assert from "node:assert/strict";
import test from "node:test";

// Công tắc MỞ QUYỀN TẠM THỜI ở tầng giao diện (Tuyền chốt 16/09/2026).
//
// Bộ kiểm chạy ở chế độ SIẾT (xem package.json: mọi lệnh test đều ghim
// MO_QUYEN_TAM_THOI=0), để các luật phân quyền gốc tiếp tục được
// canh. Bài này là ngoại lệ: nó tự bật công tắc rồi nạp lại module.
//
// `lib/roles.ts` đọc biến môi trường một lần lúc nạp module, nên phải đổi biến
// TRƯỚC rồi mới import — và import bằng đường dẫn có tham số để tránh bộ nhớ
// đệm module của Node.

async function napRoles(bat: boolean) {
  // Từ 01/10/2026 đọc LÚC GỌI (lib/cau-hinh-cong-khai.ts) — cùng tên biến với
  // backend; nạp lại module vẫn giữ để bài không phụ thuộc thứ tự chạy.
  process.env.MO_QUYEN_TAM_THOI = bat ? "1" : "0";
  return import(`../lib/roles.ts?mo=${bat}-${Math.random()}`);
}

test("công tắc BẬT: điều dưỡng mở được màn không phải của mình", async () => {
  const { canSeeNav } = await napRoles(true);
  // Đúng thứ Tuyền cần: không vai nào bị chặn khỏi màn thao tác.
  assert.equal(canSeeNav("NURSE_ULTRASOUND", "/thu-ngan/dich-vu"), true);
  assert.equal(canSeeNav("CASHIER_DV", "/truong-ca"), true);
  assert.equal(canSeeNav("TKYK", "/reception/queue"), true);
});

test("công tắc BẬT vẫn KHÔNG mở màn của người ngoài phòng khám", async () => {
  const { canSeeNav } = await napRoles(true);
  // Đối tác và cái tivi: đóng theo thiết kế. Công tắc "mở tạm" không được
  // phép chạm vào — đây là chốt chặn, không phải cách sắp xếp menu.
  assert.equal(canSeeNav("NURSE_ULTRASOUND", "/doi-tac"), false);
  assert.equal(canSeeNav("PARTNER", "/ban-kham"), false);
  assert.equal(canSeeNav("DISPLAY", "/ban-kham"), false);
});

test("công tắc BẬT vẫn KHÔNG chôn thanh bên bằng màn quản trị", async () => {
  const { canSeeNav } = await napRoles(true);
  // Không phải vì bí mật — backend vẫn gác — mà vì mở ra thì thanh bên của
  // điều dưỡng dài 35 mục và bốn mục họ cần bị đẩy xuống dưới.
  // `/console` KHÔNG nằm trong danh sách này, dù nó cũng là màn quản trị: nó
  // không có luật nào trong NAV_ROLES nên `canSeeNav` vốn đã mở cho mọi vai từ
  // trước công tắc. Không phải lỗ hổng — trang ấy `notFound()` trên production
  // và API của nó tự trả 404 khi APP_ENV=production, tức bị chặn ở hai tầng
  // khác. Ghi ra đây để lần sau đọc bài kiểm không tưởng là bỏ sót.
  for (const href of ["/settings", "/reports", "/ops"]) {
    assert.equal(
      canSeeNav("NURSE_ULTRASOUND", href),
      false,
      `${href} không được mở theo công tắc`,
    );
  }
});

test("công tắc TẮT: về đúng luật gốc", async () => {
  const { canSeeNav } = await napRoles(false);
  assert.equal(canSeeNav("NURSE_ULTRASOUND", "/thu-ngan/dich-vu"), false);
  assert.equal(canSeeNav("CASHIER_DV", "/truong-ca"), false);
  // Và những đường vốn mở thì vẫn mở.
  assert.equal(canSeeNav("NURSE_ULTRASOUND", "/home"), true);
});
