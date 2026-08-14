// Lấy CÂU cho người đọc ra khỏi thân lỗi của máy chủ.
//
// Backend trả ba dạng khác nhau, và thứ tự đọc chúng quyết định người dùng nhìn
// thấy gì:
//
//   lỗi nghiệp vụ   {"error": "CONFLICT_ERROR", "message": "Khung giờ đã đầy…"}
//   FastAPI 422     {"detail": [{"loc": [...], "msg": "…", "type": "uuid_parsing"}]}
//   route Next      {"error": "Thiếu id."}
//
// `error` ở dạng thứ nhất là MÃ CHO MÁY, ở dạng thứ ba lại là CÂU CHO NGƯỜI —
// nên không thể chỉ đọc một trường. Đọc `message` trước, rồi `detail`, rồi mới
// tới `error`: thứ tự này luôn cho ra câu dài nhất có nghĩa.
//
// Đã cắn hai lần: người thua cuộc tranh chỗ cuối nhìn thấy chữ "CONFLICT_ERROR"
// (vá 14/08/2026), và người gỡ ca trực nhìn thấy "Lỗi khi gỡ ca." trong khi máy
// chủ đang nói rõ id không phải UUID.

/** Một mục lỗi của FastAPI 422. */
interface MucLoi {
  msg?: unknown;
  loc?: unknown;
}

export function loiDocDuoc(than: unknown, mac_dinh: string): string {
  if (typeof than === "string" && than.trim()) return than.trim();
  if (!than || typeof than !== "object") return mac_dinh;
  const o = than as Record<string, unknown>;

  if (typeof o.message === "string" && o.message.trim()) return o.message.trim();

  // `detail` của FastAPI là MẢNG object, không phải chuỗi. Nối `msg` lại; ép
  // kiểu thẳng thì người dùng nhận "[object Object]" — tệ hơn câu mặc định.
  if (Array.isArray(o.detail)) {
    const cau = (o.detail as MucLoi[])
      .map((m) => (typeof m?.msg === "string" ? m.msg : ""))
      .filter(Boolean)
      .join("; ");
    if (cau) return cau;
  }
  if (typeof o.detail === "string" && o.detail.trim()) return o.detail.trim();

  // `error` đứng CUỐI: ở lỗi nghiệp vụ nó là mã máy ("CONFLICT_ERROR"), chỉ
  // dùng khi không còn gì đọc được. Mã in hoa toàn phần thì thà lấy mặc định —
  // câu tiếng Việt còn nói được nhiều hơn một mã.
  if (typeof o.error === "string" && o.error.trim()) {
    const e = o.error.trim();
    return /^[A-Z][A-Z0-9_]+$/.test(e) ? mac_dinh : e;
  }
  return mac_dinh;
}
