// Cửa BFF của ĐỐI TÁC — hai việc, không hơn.
//
//   GET   → việc trên bàn đối tác (`?ngay=` xem ngày cũ)
//   POST  → gửi một tệp kết quả cho MỘT chỉ định (multipart: chi_dinh_id, file)
//
// Không đụng database ở đây. Cả hai đi thẳng FastAPI, nơi `get_partner_identity`
// gác và nơi truy vấn lọc theo `node_definition.lam_ben_ngoai`. Lớp này chỉ làm
// một việc: chứng minh người gọi đã đăng nhập, rồi chuyển tiếp.

import { NextResponse } from "next/server";
import { chuyenTiepTaiLen } from "@/lib/chuyen-tiep-tai-len";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { fetchFromBackend, getCallerAuthHeaders } from "../../../lib/backend-proxy";

const API_BASE = (process.env.CLINIC_API_URL ?? "").trim().replace(/\/$/, "");

const NGAY_RE = /^\d{4}-\d{2}-\d{2}$/;

export async function GET(request: Request) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Chưa đăng nhập" }, { status: 401 });

  // `?ngay=YYYY-MM-DD` (29/09/2026): xem việc của một ngày cũ. Sai dạng thì bỏ —
  // máy chủ coi như hôm nay (máy chủ vẫn tự đọc lại, rác không thành 500).
  const ngay = new URL(request.url).searchParams.get("ngay") ?? "";
  const d = await fetchFromBackend<{ khach: unknown[]; so_viec: number }>(
    NGAY_RE.test(ngay)
      ? `/api/v1/doi-tac/viec?ngay=${encodeURIComponent(ngay)}`
      : "/api/v1/doi-tac/viec",
  );
  if (d === null) {
    // null = không với tới backend. Trả mảng rỗng ở đây thì màn nói dối "không
    // có khách nào", và đối tác đóng tab đi về trong khi kết quả vẫn đang chờ.
    return NextResponse.json(
      { error: "Không đọc được danh sách khách" },
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
  // KHÔNG chặn theo dung lượng (Tuyền chốt 16/09/2026: không giới hạn).
  if (clIn) headers["Content-Length"] = clIn;

  let res: { status: number; text: string };
  try {
    res = await chuyenTiepTaiLen(`${API_BASE}/api/v1/doi-tac/ket-qua`, request, headers);
  } catch {
    return NextResponse.json(
      { error: "Mất kết nối giữa chừng — tệp CHƯA được lưu, hãy tải lại." },
      { status: 502 },
    );
  }

  const text = res.text;
  let payload: unknown = {};
  try {
    payload = text ? JSON.parse(text) : {};
  } catch {
    payload = { error: text.slice(0, 300) };
  }
  return NextResponse.json(payload, { status: res.status });
}
