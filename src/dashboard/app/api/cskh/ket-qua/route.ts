// Tệp kết quả khám — tải lên, liệt kê, đánh dấu đã gửi.
//
//   GET   ?clinic_patient_id=…            → danh sách tệp của khách
//   POST  (multipart: file, clinic_patient_id[, appointment_id])
//   PATCH { id, kenh }                    → CSKH xác nhận đã gửi
//
// Đi qua FastAPI (ADR-0012): khoá tệp do hệ thống sinh, người tải lên lấy từ
// phiên. Nội dung tệp KHÔNG đi qua route này — xem `[tepId]/noi-dung`, nó phải
// chảy theo luồng và hiểu HTTP Range để video xem được.

import { NextResponse } from "next/server";
import {
  fetchFromBackend,
  getCallerAuthHeaders,
  proxyJsonToBackend,
} from "../../../../lib/backend-proxy";

const API_BASE = process.env.CLINIC_API_URL;

export async function GET(request: Request) {
  const id = (
    new URL(request.url).searchParams.get("clinic_patient_id") ?? ""
  ).trim();
  if (!id) {
    return NextResponse.json({ error: "Thiếu mã khách hàng." }, { status: 400 });
  }
  const data = await fetchFromBackend<{ items: unknown[] }>(
    `/api/v1/cskh/ket-qua/${encodeURIComponent(id)}`,
  );
  // null = không gọi được backend. Trả 503 chứ đừng trả danh sách rỗng: "chưa
  // có kết quả nào" và "không đọc được" là hai chuyện khác hẳn, và cái thứ hai
  // hiện thành cái thứ nhất sẽ khiến CSKH tải lên lần thứ hai.
  if (data === null) {
    return NextResponse.json(
      { error: "Không đọc được danh sách kết quả." },
      { status: 503 },
    );
  }
  return NextResponse.json(data);
}

export async function POST(request: Request) {
  if (!API_BASE) {
    return NextResponse.json(
      { error: "CLINIC_API_URL chưa được cấu hình trên server." },
      { status: 503 },
    );
  }
  const headers = await getCallerAuthHeaders();
  if (!headers) {
    return NextResponse.json({ error: "Chưa đăng nhập" }, { status: 401 });
  }

  // CHUYỂN TIẾP NGUYÊN VĂN multipart. Đọc rồi dựng lại FormData ở đây là nạp
  // cả tệp vào RAM của tiến trình Next — với video 80MB thì đó là 80MB mỗi
  // lượt tải, trên cùng một máy đang chạy database.
  //
  // PHẢI CHUYỂN TIẾP Content-Type, VÀ ĐÂY LÀ CHỖ ĐÃ SAI MỘT LẦN.
  //
  // Bản đầu cố ý bỏ header này ("boundary nằm trong header gốc") — nhưng
  // `getCallerAuthHeaders()` chỉ trả Authorization + X-API-Key, nên header gốc
  // KHÔNG đi cùng. FastAPI nhận một thân multipart mà không biết boundary, và
  // trả 422 "clinic_patient_id: Field required" — nghe như client quên gửi
  // trường, trong khi trường ấy nằm ngay trong thân không đọc được.
  //
  // Gọi thẳng API bằng script thì chạy (script tự đặt Content-Type), nên lỗi
  // chỉ lộ ra khi bấm nút thật trên trình duyệt.
  const ctIn = request.headers.get("content-type");
  if (ctIn) headers["Content-Type"] = ctIn;
  const clIn = request.headers.get("content-length");
  if (clIn) headers["Content-Length"] = clIn;

  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/v1/cskh/ket-qua/tep`, {
      method: "POST",
      headers,
      body: request.body,
      // @ts-expect-error — `duplex` là bắt buộc của undici khi body là luồng;
      // kiểu của Next chưa khai nó.
      duplex: "half",
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
  if (!res.ok && payload && typeof payload === "object" && "message" in payload) {
    const msg = (payload as { message?: string }).message;
    return NextResponse.json({ error: msg ?? "Lỗi xử lý" }, { status: res.status });
  }
  return NextResponse.json(payload, { status: res.status });
}

export async function PATCH(request: Request) {
  let body: { id?: string; kenh?: string };
  try {
    body = (await request.json()) as typeof body;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const id = (body.id ?? "").trim();
  if (!id) return NextResponse.json({ error: "Thiếu id tệp." }, { status: 400 });
  return proxyJsonToBackend(
    "POST",
    `/api/v1/cskh/ket-qua/tep/${encodeURIComponent(id)}/da-gui`,
    { kenh: body.kenh },
  );
}
