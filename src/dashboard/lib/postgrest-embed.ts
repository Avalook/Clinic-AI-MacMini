// Quan hệ nhúng của PostgREST: MỘT hay NHIỀU, tuỳ chiều khoá ngoại.
//
// LỖI ĐÃ CÓ THẬT, đo trên production ngày 07/08/2026.
//
// Bốn màn nhà thuốc (và màn Duyệt kết quả) chuẩn hoá quan hệ nhúng bằng
// `x?.[0] ?? null`, kèm chú thích "Supabase trả FK relationship dạng mảng".
// Điều đó đúng với quan hệ MỘT-NHIỀU (nhìn từ phía "một"), nhưng cả năm chỗ ấy
// đều là NHIỀU-MỘT — `drug_batch → drug_catalog`, `prescription → patient` —
// và PostgREST trả về một OBJECT:
//
//     {"id":"…","batch_code":"UI-…","drug":{"name_base":"Androgel"}}
//
// Lấy `[0]` của một object cho `undefined`, rồi `?? null` biến nó thành `null`.
// Không lỗi, không cảnh báo — chỉ là mọi đơn thuốc hiện "Chưa có tên" và mọi
// lô hiện "Chưa đặt tên", suốt từ ngày màn hình được viết.
//
// Hàm này nhận CẢ HAI hình dạng. Không phải để chiều sự mơ hồ: PostgREST đổi
// hình dạng theo chiều khoá ngoại, và người viết màn hình không nên phải nhớ
// chiều ấy để hiển thị đúng một cái tên.

/** Lấy bản ghi ĐƠN từ một quan hệ nhúng, dù PostgREST trả object hay mảng. */
export function motBanGhi<T>(value: T | T[] | null | undefined): T | null {
  if (value == null) return null;
  if (Array.isArray(value)) return value[0] ?? null;
  return value;
}
