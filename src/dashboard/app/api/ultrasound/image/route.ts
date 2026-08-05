// Ảnh siêu âm — đường tải lên và đường xem.
//
// KHÔNG DÙNG `proxyJsonToBackend`: helper ấy chỉ biết JSON. Ở đây một chiều là
// multipart (tệp ảnh) và chiều kia là nhị phân (chính tấm ảnh), nên phải truyền
// thẳng luồng.
//
// TUYỆT ĐỐI KHÔNG ĐỌC ẢNH VÀO BỘ NHỚ RỒI DỰNG LẠI. Ảnh siêu âm tới 12MB; đọc
// vào chuỗi rồi ghép lại vừa tốn gấp đôi bộ nhớ vừa hỏng byte. `body` của
// Request truyền được nguyên xi.
//
// KHÔNG CÓ LUẬT NÀO Ở FILE NÀY. Kiểu tệp kiểm bằng magic bytes, giới hạn 12MB,
// tên tệp do hệ thống đặt, và "phiếu đã ký thì khoá" — tất cả ở
// `services/media_service.py`. Một bản sao ở đây là một bản sẽ lệch, và lệch ở
// đúng chỗ quyết định "tệp này có phải ảnh không".

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../../lib/supabase-server";

const API_BASE = (process.env.CLINIC_API_URL ?? "").trim().replace(/\/$/, "");

/** Header xác thực: token của người đang đăng nhập + khoá dùng chung. */
async function authHeaders(): Promise<Record<string, string> | null> {
  const supabase = await getSupabaseServer();
  // `getUser()` trước `getSession()`: getSession KHÔNG làm mới token hết hạn,
  // getUser thì có. Đảo thứ tự là thỉnh thoảng gửi đi một token đã chết.
  await supabase.auth.getUser();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session?.access_token) return null;

  const h: Record<string, string> = {
    Authorization: `Bearer ${session.access_token}`,
  };
  const apiKey = process.env.BACKEND_API_KEY;
  if (apiKey) h["X-API-Key"] = apiKey;
  return h;
}

/** POST /api/ultrasound/image?id=<ultrasound_id> — tải một ảnh lên. */
export async function POST(request: Request) {
  if (!API_BASE) {
    return NextResponse.json(
      { error: "CLINIC_API_URL chưa được cấu hình trên server." },
      { status: 503 },
    );
  }
  const headers = await authHeaders();
  if (!headers)
    return NextResponse.json({ error: "Chưa đăng nhập" }, { status: 401 });

  const id = new URL(request.url).searchParams.get("id");
  if (!id)
    return NextResponse.json(
      { error: "Thiếu mã bản ghi siêu âm." },
      { status: 400 },
    );

  // Đọc lại thành FormData rồi gửi đi, thay vì chuyển tiếp `request.body` thô:
  // `fetch` phải tự đặt lại boundary của multipart, và boundary cũ trong header
  // Content-Type sẽ không khớp với thân đã đi qua một chặng.
  const form = await request.formData();
  const file = form.get("file");
  if (!(file instanceof File))
    return NextResponse.json({ error: "Chưa chọn tệp." }, { status: 400 });

  const gui = new FormData();
  gui.append("file", file, file.name);

  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/v1/ultrasound/${id}/image`, {
      method: "POST",
      headers, // KHÔNG đặt Content-Type — fetch tự sinh kèm boundary đúng.
      body: gui,
      cache: "no-store",
    });
  } catch {
    return NextResponse.json(
      { error: "Không kết nối được máy chủ xử lý" },
      { status: 502 },
    );
  }

  const text = await res.text();
  let payload: unknown = {};
  try {
    payload = text ? JSON.parse(text) : {};
  } catch {
    payload = { error: text || "Lỗi máy chủ" };
  }
  // FastAPI trả lỗi nghiệp vụ dạng { error, message } — đưa `message` ra màn
  // hình, vì đó là câu người vận hành đọc được ("Kết quả đã ký — không thêm ảnh
  // được").
  if (!res.ok && payload && typeof payload === "object" && "message" in payload) {
    return NextResponse.json(
      { error: String((payload as { message: unknown }).message) },
      { status: res.status },
    );
  }
  return NextResponse.json(payload, { status: res.status });
}

/** GET /api/ultrasound/image?key=<khoá> — xem một ảnh. */
export async function GET(request: Request) {
  if (!API_BASE)
    return new NextResponse("CLINIC_API_URL chưa cấu hình", { status: 503 });

  const headers = await authHeaders();
  if (!headers) return new NextResponse("Chưa đăng nhập", { status: 401 });

  const key = new URL(request.url).searchParams.get("key");
  if (!key) return new NextResponse("Thiếu khoá ảnh", { status: 400 });

  let res: Response;
  try {
    res = await fetch(
      `${API_BASE}/api/v1/ultrasound/image?key=${encodeURIComponent(key)}`,
      { headers, cache: "no-store" },
    );
  } catch {
    return new NextResponse("Không kết nối được máy chủ xử lý", { status: 502 });
  }
  if (!res.ok) return new NextResponse(await res.text(), { status: res.status });

  // Trả nguyên luồng nhị phân. Giữ lại hai header bảo vệ mà backend đã đặt:
  // `private` để proxy dùng chung không giữ ảnh bệnh nhân, và `nosniff` để
  // trình duyệt không tự đoán kiểu rồi chạy nội dung như HTML.
  return new NextResponse(res.body, {
    status: 200,
    headers: {
      "Content-Type": res.headers.get("content-type") ?? "application/octet-stream",
      "Cache-Control": "private, max-age=300",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
