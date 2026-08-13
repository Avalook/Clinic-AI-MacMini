// Khoá chống-ghi-hai-lần cho các nút CSKH.
//
// VÌ SAO CẦN, đo trên staging 11/08/2026:
//
//   · Ngắt mạng ở mốc 90ms sau khi bấm → màn hình báo LỖI MẠNG trong khi dòng
//     sổ ĐÃ ĐƯỢC GHI. Người trực nhập lại, và lần nhập lại tạo dòng thứ hai.
//     Ngắt ở 30ms thì không. Tức có một cửa sổ vài chục mili-giây mà màn hình
//     nói một đằng, dữ liệu một nẻo — và phòng khám thì wifi chập chờn.
//   · Bấm nút hai lần thật nhanh → hai dòng, cách nhau 0,35ms.
//
// Hai dòng "Đã gọi nhắc hẹn" trong lịch sử một khách đọc thành đã gọi hai lần.
// Không hỏng dữ liệu, nhưng làm người sau tin sai về việc đã làm.
//
// CÁCH LÀM: mỗi THAO TÁC (không phải mỗi lần bấm) có một khoá. Bấm lần hai của
// cùng thao tác, hoặc gửi lại sau khi mạng rớt, đều mang lại đúng khoá cũ — nên
// backend nhận ra và trả lại kết quả lần đầu thay vì ghi thêm. Khoá chỉ bị bỏ
// khi thao tác THÀNH CÔNG, hoặc khi người dùng đổi sang thao tác khác.
//
// Đây là lý do khoá KHÔNG sinh mới mỗi lần bấm: sinh mới thì mỗi lần bấm là một
// thao tác khác nhau dưới mắt backend, và chốt chống trùng thành vô nghĩa.

const dangMo = new Map<string, string>();

/**
 * Khoá cho một thao tác. Gọi bao nhiêu lần cũng trả về CÙNG một chuỗi, cho tới
 * khi `xongThaoTac(dinhDanh)` được gọi.
 *
 * `dinhDanh` phải mô tả THAO TÁC, không phải lần bấm: gồm khách nào, việc gì,
 * trạng thái nào. Hai thao tác khác nhau phải ra hai định danh khác nhau, nếu
 * không thao tác thứ hai sẽ bị nuốt mất vì trùng khoá với thao tác thứ nhất.
 */
export function khoaThaoTac(dinhDanh: string): string {
  const co = dangMo.get(dinhDanh);
  if (co) return co;
  const moi =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : // Trình duyệt cũ hoặc ngữ cảnh không an toàn (http). Phòng khám chạy
        // trên http nội bộ, nên nhánh này KHÔNG phải lý thuyết.
        `k-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
  dangMo.set(dinhDanh, moi);
  return moi;
}

/** Thao tác đã xong — lần bấm sau là một thao tác MỚI, phải có khoá mới. */
export function xongThaoTac(dinhDanh: string): void {
  dangMo.delete(dinhDanh);
}

/** Dựng định danh thao tác từ các mảnh. Bỏ mảnh rỗng để không sinh "a::b". */
export function dinhDanhThaoTac(...manh: (string | null | undefined)[]): string {
  return manh.filter(Boolean).join("|");
}
