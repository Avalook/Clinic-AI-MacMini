// Đọc câu lỗi của backend — MỘT chỗ, vì backend nói bằng HAI hình dạng.
//
// LỖI QUANG GẶP 10/08/2026: bấm mấy nút dưới bước check-in thì hiện "Không ghi
// được (lỗi 429)". Con số ấy không nói gì, và tệ hơn: backend ĐÃ gửi kèm một
// câu tiếng Việt đọc được — chỉ là màn hình tìm nó ở sai chỗ.
//
//   Ngoại lệ CỦA ỨNG DỤNG   → {"error": "...", "message": "câu tiếng Việt"}
//                              (main.py, clinicai_exception_handler)
//   `HTTPException` của FastAPI → {"detail": "câu tiếng Việt"}
//                              (runaway_guard, rate_limit, và mọi chỗ raise trần)
//
// Mọi màn đều chỉ đọc `message ?? error`, nên NHÓM THỨ HAI luôn rơi xuống câu
// mặc định kèm mã số. Nghĩa là chính những lỗi cần giải thích nhất — quá nhiều
// yêu cầu, sai định dạng, thiếu quyền — lại là nhóm im lặng nhất.
//
// Viết ở đây thay vì thêm một `?? d?.detail` vào mười chỗ: mười bản chép tay là
// mười chỗ sẽ quên nhóm thứ ba khi nó xuất hiện.

/** Thân phản hồi lỗi, ở bất kỳ hình dạng nào backend dùng. */
export interface ThanLoi {
  error?: string;
  message?: string;
  detail?: unknown;
}

/** Câu lỗi đọc được cho người dùng. `macDinh` dùng khi backend không nói gì. */
export function nhanLoi(d: ThanLoi | null | undefined, macDinh: string): string {
  const chu = d?.message ?? d?.error ?? doDetail(d?.detail);
  return (chu ?? "").trim() || macDinh;
}

/** `detail` của FastAPI có thể là chuỗi, hoặc mảng lỗi kiểm tra của Pydantic. */
function doDetail(detail: unknown): string | undefined {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // 422 của Pydantic: [{loc: [...], msg: "...", type: "..."}]. Lấy `msg` —
    // ghép cả mảng thành một dòng dài thì không ai đọc.
    const dau = detail.find(
      (x): x is { msg?: unknown } =>
        typeof x === "object" && x !== null && "msg" in x,
    );
    if (dau && typeof dau.msg === "string") return dau.msg;
  }
  return undefined;
}
