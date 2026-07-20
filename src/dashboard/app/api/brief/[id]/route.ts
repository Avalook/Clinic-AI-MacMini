// /api/brief/[id]
//   POST → sinh "tóm tắt trước khám" cho 1 bệnh nhân.
//
// CẦU NỐI ĐẦU TIÊN dashboard → FastAPI. Mọi route khác đọc/ghi thẳng Supabase;
// riêng tóm tắt do FastAPI lo (POST /api/v1/brief/{id}) vì cần LLM + tổng hợp
// nhiều bảng. Proxy CHẠY PHÍA SERVER nên:
//   - KHÔNG dính CORS (server→server, không phải trình duyệt→FastAPI),
//   - giữ BACKEND_API_KEY ở server (không lộ ra bundle trình duyệt).
//
// CHỈ gọi-và-trả, KHÔNG lưu kết quả vào DB.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../../lib/supabase-server";
import { getClinicRole, getClinicStaffId } from "../../../../lib/clinic-session";
import { isDoctorRole } from "../../../../lib/roles";

// FastAPI base URL. Server-only (không phải NEXT_PUBLIC) vì lời gọi đi từ server.
// Mặc định localhost:8000 để dev không cần cấu hình gì thêm.
const API_BASE = process.env.CLINIC_API_URL ?? "http://localhost:8000";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;

  // 1) Phải đăng nhập (cổng chung Supabase).
  const supabase = await getSupabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Chưa đăng nhập." }, { status: 401 });
  }

  // 2) Tóm tắt trước khám là dành cho BÁC SĨ.
  const role = await getClinicRole();
  if (!isDoctorRole(role)) {
    return NextResponse.json(
      { error: "Chỉ bác sĩ mới xem được tóm tắt trước khám." },
      { status: 403 },
    );
  }

  if (!UUID_RE.test(id)) {
    return NextResponse.json(
      { error: "Mã bệnh nhân không hợp lệ." },
      { status: 400 },
    );
  }

  // 3) Bác sĩ chỉ tóm tắt BN CỦA MÌNH (mirror guard ở patients/[id]) — không nới
  // quyền: phải có ít nhất 1 lịch hẹn giữa bác sĩ này và bệnh nhân.
  const staffId = await getClinicStaffId();
  let own = true;
  if (role !== "TKYK") {
    const { data: ownAppt } = await supabase
      .from("appointment")
      .select("id")
      .eq("doctor_id", staffId)
      .eq("clinic_patient_id", id)
      .limit(1)
      .maybeSingle();
    own = !!ownAppt;
  }
  if (!own) {
    return NextResponse.json(
      { error: "Bệnh nhân này không thuộc lịch khám của bạn." },
      { status: 403 },
    );
  }

  // 4) Proxy sang FastAPI. Forward X-API-Key nếu server có cấu hình (production);
  // dev để trống thì FastAPI tự cho qua.
  const headers: Record<string, string> = {};
  const apiKey = process.env.BACKEND_API_KEY;
  if (apiKey) headers["X-API-Key"] = apiKey;

  // Tóm tắt gọi LLM → có thể vài giây. Đặt trần 60s để backend treo không kéo
  // theo request này treo mãi.
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 60_000);

  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/v1/brief/${id}`, {
      method: "POST",
      headers,
      signal: controller.signal,
      cache: "no-store",
    });
  } catch {
    // ECONNREFUSED / timeout / DNS… — KHÔNG echo chi tiết (có thể lộ nội bộ).
    return NextResponse.json(
      {
        error:
          "Không kết nối được máy chủ tóm tắt. Kiểm tra dịch vụ FastAPI đã bật chưa.",
      },
      { status: 502 },
    );
  } finally {
    clearTimeout(timeout);
  }

  if (res.status === 404) {
    return NextResponse.json(
      { error: "Không tìm thấy bệnh nhân để tóm tắt." },
      { status: 404 },
    );
  }
  if (res.status === 401 || res.status === 403) {
    return NextResponse.json(
      { error: "Sai cấu hình khóa API giữa dashboard và máy chủ tóm tắt." },
      { status: 502 },
    );
  }
  if (!res.ok) {
    return NextResponse.json(
      { error: "Máy chủ tóm tắt gặp lỗi khi tạo tóm tắt. Thử lại sau." },
      { status: 502 },
    );
  }

  let payload: { markdown?: string; elapsed_ms?: number };
  try {
    payload = (await res.json()) as { markdown?: string; elapsed_ms?: number };
  } catch {
    return NextResponse.json(
      { error: "Máy chủ tóm tắt trả dữ liệu không đọc được." },
      { status: 502 },
    );
  }

  // Chỉ chuyển phần markdown + thời gian; KHÔNG lưu, KHÔNG log nội dung BN.
  return NextResponse.json({
    markdown: payload.markdown ?? "",
    elapsed_ms: payload.elapsed_ms ?? null,
  });
}
