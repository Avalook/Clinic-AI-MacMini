// Nội dung một tệp kết quả — CHẢY THEO LUỒNG, và chuyển tiếp HTTP Range.
//
// Tách khỏi route liệt kê vì nó khác về bản chất: ở đây không có JSON nào cả,
// chỉ có byte. Và ba thứ phải giữ nguyên từ backend sang trình duyệt:
//
//   · `Range` đi LÊN, `Content-Range` + 206 đi XUỐNG — không có chúng thì
//     trình duyệt phải tải trọn video trước khi phát được giây đầu, và thanh
//     tua không kéo được.
//   · Thân trả về là LUỒNG (`res.body`), không `await res.arrayBuffer()`:
//     đọc cả tệp vào RAM của tiến trình Next là 80MB mỗi người xem.
//   · `X-Content-Type-Options: nosniff` — đây là dữ liệu bệnh nhân, và một
//     tệp được đoán nhầm kiểu là một tệp trình duyệt có thể chạy.

import { NextResponse } from "next/server";
import { getCallerAuthHeaders } from "../../../../../../lib/backend-proxy";

const API_BASE = process.env.CLINIC_API_URL;

export async function GET(
  request: Request,
  ctx: { params: Promise<{ tepId: string }> },
) {
  if (!API_BASE) {
    return NextResponse.json(
      { error: "CLINIC_API_URL chưa được cấu hình trên server." },
      { status: 503 },
    );
  }
  const auth = await getCallerAuthHeaders();
  if (!auth) {
    return NextResponse.json({ error: "Chưa đăng nhập" }, { status: 401 });
  }
  const { tepId } = await ctx.params;
  const id = (tepId ?? "").trim();
  if (!id) return NextResponse.json({ error: "Thiếu id tệp." }, { status: 400 });

  const headers: Record<string, string> = { ...auth };
  const rng = request.headers.get("range");
  if (rng) headers["Range"] = rng;

  let res: Response;
  try {
    res = await fetch(
      `${API_BASE}/api/v1/cskh/ket-qua/tep/${encodeURIComponent(id)}/noi-dung`,
      { headers, cache: "no-store" },
    );
  } catch {
    return NextResponse.json(
      { error: "Không kết nối được máy chủ xử lý" },
      { status: 502 },
    );
  }

  const ra: Record<string, string> = {
    "X-Content-Type-Options": "nosniff",
    // Máy/quầy dùng chung: sau logout hoặc đổi tài khoản, PHI không được lấy
    // lại từ browser cache mà bỏ qua authorization của request mới.
    "Cache-Control": "private, no-store",
  };
  for (const h of [
    "content-type",
    "content-length",
    "content-range",
    "accept-ranges",
    "content-disposition",
  ]) {
    const v = res.headers.get(h);
    if (v) ra[h] = v;
  }
  return new Response(res.body, { status: res.status, headers: ra });
}
