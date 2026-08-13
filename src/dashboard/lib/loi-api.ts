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

// NHÓM THỨ BA, tìm được khi nghiệm thu 11/08/2026 — đúng như dòng cảnh báo phía trên.
//
//   Kiểm tra dữ liệu 422 → {"error": [{loc, msg, type, input}, …]}
//
// Mảng Pydantic nằm ở `error`, KHÔNG phải ở `detail`. Bản trước có sẵn `doDetail()`
// viết riêng cho hình dạng mảng ấy — nhưng gắn vào sai ô, nên không bao giờ chạy tới.
// Đúng hình dạng, sai chỗ.
//
// Hậu quả không phải là hiện sai chữ, mà là NỔ: `chu` nhận nguyên mảng, rồi
// `(chu ?? "").trim()` gọi `.trim()` trên một Array →
//     TypeError: (chu ?? "").trim is not a function
// Trình xử lý lỗi tự nó chết, nên nhân viên gõ sai ngày sinh sẽ bấm Lưu và thấy
// KHÔNG GÌ CẢ — không câu báo, không dấu hiệu. Tệ hơn hẳn một câu khó hiểu.
//
// Vì thế bản này không đoán hình dạng nữa: MỌI ứng viên đều đi qua `doCau()`, và
// `doCau()` chỉ trả về chuỗi hoặc undefined. Thêm ô thứ tư cũng không nổ được.

/** Thân phản hồi lỗi, ở bất kỳ hình dạng nào backend dùng. */
export interface ThanLoi {
  error?: unknown;
  message?: unknown;
  detail?: unknown;
}

/** Câu lỗi đọc được cho người dùng. `macDinh` dùng khi backend không nói gì. */
export function nhanLoi(d: ThanLoi | null | undefined, macDinh: string): string {
  const chu = doCau(d?.message) ?? doCau(d?.error) ?? doCau(d?.detail);
  return (chu ?? "").trim() || macDinh;
}

/** Tên ô trong dữ liệu → tên người trực gọi nó. Chỉ những ô vùng CSKH thật sự gõ. */
const TEN_O: Record<string, string> = {
  date_of_birth: "Ngày sinh",
  phone_primary: "Số điện thoại",
  phone_secondary: "Số điện thoại phụ",
  full_name: "Họ tên",
  national_id_number: "Số CCCD",
  slot_start: "Giờ khám",
  scheduled_at: "Giờ khám",
  service_type_id: "Dịch vụ",
  location_id: "Cơ sở",
  doctor_id: "Bác sĩ",
  ngay_hen: "Ngày hẹn",
  noi_dung: "Nội dung",
};

/**
 * Rút một câu đọc được từ BẤT KỲ hình dạng nào — chuỗi, mảng lỗi Pydantic, hay
 * một đối tượng lẻ. Không bao giờ ném, không bao giờ trả về thứ không phải chuỗi.
 */
function doCau(v: unknown): string | undefined {
  if (typeof v === "string") return v.trim() || undefined;

  if (Array.isArray(v)) {
    // 422 của Pydantic: [{loc: ["body","date_of_birth"], msg: "...", type: "..."}].
    // Lấy lỗi ĐẦU TIÊN — ghép cả mảng thành một dòng dài thì không ai đọc.
    for (const x of v) {
      const cau = doCau(x);
      if (cau) return cau;
    }
    return undefined;
  }

  if (typeof v === "object" && v !== null) {
    const o = v as { msg?: unknown; message?: unknown; loc?: unknown };
    const goc = typeof o.msg === "string" ? o.msg : o.message;
    if (typeof goc !== "string" || !goc.trim()) return undefined;

    // Gắn tên ô vào câu. Câu gốc của Pydantic bằng tiếng Anh và không nói ô nào —
    // "Input should be a valid date" thì người trực không biết sửa chỗ nào.
    const ten = tenOTu(o.loc);
    return ten ? `${ten}: ${doiCauQuen(goc)}` : doiCauQuen(goc);
  }

  return undefined;
}

/** `loc: ["body","date_of_birth"]` → "Ngày sinh". */
function tenOTu(loc: unknown): string | undefined {
  if (!Array.isArray(loc)) return undefined;
  for (let i = loc.length - 1; i >= 0; i--) {
    const p = loc[i];
    if (typeof p === "string" && p !== "body" && p !== "query") {
      return TEN_O[p] ?? p;
    }
  }
  return undefined;
}

/** Vài câu Pydantic hay gặp nhất, nói lại bằng tiếng Việt. Câu lạ thì giữ nguyên. */
function doiCauQuen(msg: string): string {
  const m = msg.toLowerCase();
  if (m.includes("valid date")) return "ngày không hợp lệ.";
  if (m.includes("valid integer") || m.includes("valid number"))
    return "phải là một con số.";
  if (m.includes("field required")) return "chưa nhập.";
  if (m.includes("valid uuid")) return "giá trị không hợp lệ.";
  if (m.includes("too_short") || m.includes("at least"))
    return "nhập quá ngắn.";
  if (m.includes("too_long") || m.includes("at most")) return "nhập quá dài.";
  return msg;
}
