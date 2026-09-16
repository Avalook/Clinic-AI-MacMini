// Cửa BFF của ĐỐI TÁC — hai việc, không hơn.
//
//   GET   → danh sách chỉ định gửi ra ngoài chưa có kết quả
//   POST  → gửi một tệp kết quả cho MỘT chỉ định (multipart: chi_dinh_id, file)
//
// Không đụng database ở đây. Cả hai đi thẳng FastAPI, nơi `get_partner_identity`
// gác và nơi truy vấn lọc theo `node_definition.lam_ben_ngoai`. Lớp này chỉ làm
// một việc: chứng minh người gọi đã đăng nhập, rồi chuyển tiếp.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { fetchFromBackend, getCallerAuthHeaders } from "../../../lib/backend-proxy";

const API_BASE = (process.env.CLINIC_API_URL ?? "").trim().replace(/\/$/, "");

export async function GET() {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Chưa đăng nhập" }, { status: 401 });

  const d = await fetchFromBackend<{ items: unknown[] }>("/api/v1/doi-tac/viec");
  if (d === null) {
    // null = không với tới backend. Trả mảng rỗng ở đây thì màn nói dối "không
    // có việc nào", và đối tác đóng tab đi về trong khi kết quả vẫn đang chờ.
    return NextResponse.json(
      { error: "Không đọc được danh sách việc" },
      { status: 502 },
    );
  }
  return NextResponse.json(d, { headers: { "Cache-Control": "private, no-store" } });
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

  // Chuyển tiếp NGUYÊN VĂN luồng multipart — đọc rồi dựng lại FormData ở đây là
  // nạp cả tệp vào RAM của tiến trình Next.
  //
  // PHẢI kèm Content-Type: `getCallerAuthHeaders()` chỉ trả Authorization +
  // X-API-Key, nên header gốc KHÔNG tự đi theo, và FastAPI nhận một thân
  // multipart không biết boundary rồi trả 422 "thiếu trường" — nghe như lỗi của
  // người gửi, trong khi trường ấy nằm ngay trong thân không đọc được. Cửa tải
  // tệp của CSKH đã cắn đúng lỗi này một lần.
  const ctIn = request.headers.get("content-type");
  if (ctIn) headers["Content-Type"] = ctIn;
  const clIn = request.headers.get("content-length");
  if (clIn) headers["Content-Length"] = clIn;

  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/v1/doi-tac/ket-qua`, {
      method: "POST",
      headers,
      body: request.body,
      // @ts-expect-error — `duplex` là bắt buộc của undici khi body là luồng.
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
    payload = { error: text.slice(0, 300) };
  }
  return NextResponse.json(payload, { status: res.status });
}
