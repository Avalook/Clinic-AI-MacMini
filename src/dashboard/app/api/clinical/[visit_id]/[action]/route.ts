// Ký / cho phép gửi / đính chính — proxy xuống FastAPI.
//
// Danh sách trắng thao tác, không phải [action] trần: một tham số tự do sẽ cho
// gọi bất kỳ đường nào dưới /api/v1/clinical/, kể cả đường thêm sau này mà chưa
// ai cân nhắc có nên mở ra trình duyệt không.
//
// KHÔNG gác vai ở đây. Backend chặn (require_role DOCTOR / ULTRASOUND_DOCTOR),
// và ký bệnh án là chỗ duy nhất trong hệ thống mà một lớp gác thừa ở proxy có
// thể LÀM HẠI: nếu danh sách vai ở hai nơi lệch nhau, bác sĩ thật sẽ bị chặn
// bởi lớp sai. Một nguồn sự thật, và nó nằm cạnh dữ liệu.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../../../lib/supabase-server";
import { proxyJsonToBackend, fetchFromBackend } from "../../../../../lib/backend-proxy";

const ACTIONS = new Set(["sign", "release", "amend"]);

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ visit_id: string; action: string }> },
) {
  const supabase = await getSupabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  const { visit_id, action } = await params;
  if (action !== "status") {
    return NextResponse.json({ error: "Không hỗ trợ" }, { status: 400 });
  }
  // ĐỌC mở cho mọi vai lâm sàng: CSKH cần biết đã được phép gửi chưa, Điều
  // dưỡng cần biết hồ sơ đã khoá chưa.
  const data = await fetchFromBackend<unknown>(
    `/api/v1/clinical/${encodeURIComponent(visit_id)}/status`,
  );
  return NextResponse.json(data ?? { error: "Không đọc được trạng thái" });
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ visit_id: string; action: string }> },
) {
  const supabase = await getSupabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  const { visit_id, action } = await params;
  if (!ACTIONS.has(action)) {
    return NextResponse.json(
      { error: `Thao tác không hợp lệ: ${action}` },
      { status: 400 },
    );
  }

  let body: unknown = {};
  try {
    body = await request.json();
  } catch {
    body = {};
  }
  return proxyJsonToBackend(
    "POST",
    `/api/v1/clinical/${encodeURIComponent(visit_id)}/${action}`,
    body,
  );
}
