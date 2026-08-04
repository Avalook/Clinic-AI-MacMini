// Đường ĐỌC + GHI của bộ phận Siêu âm — chỉ chuyển tiếp xuống FastAPI.
//
// Không có luật nào ở đây. Ai được xem, bốn ô "sẵn sàng" tính thế nào, bản đã
// ký có sửa được không — tất cả nằm ở ultrasound_board_service.py. Một bản sao
// luật ở tầng proxy là một bản sẽ lệch, và lệch ở đúng chỗ quyết định "bệnh
// nhân này đã đủ điều kiện siêu âm chưa".
import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { fetchFromBackend, proxyJsonToBackend } from "../../../lib/backend-proxy";

async function requireUser() {
  const supabase = await getSupabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  return user;
}

export async function GET(request: Request) {
  if (!(await requireUser()))
    return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  const sp = new URL(request.url).searchParams;
  const what = sp.get("what") ?? "queue";
  const path =
    what === "rooms"
      ? "/api/v1/ultrasound/rooms"
      : what === "records"
        ? `/api/v1/ultrasound/records?signed=${sp.get("signed") === "true"}` +
          `&days=${encodeURIComponent(sp.get("days") ?? "1")}`
        : "/api/v1/ultrasound/queue";

  const data = await fetchFromBackend<Record<string, unknown>>(path);
  // `null` = máy chủ xử lý không trả lời. Nói ra thay vì trả danh sách rỗng —
  // một hàng chờ trống trông y hệt "không còn ai cần siêu âm".
  if (data === null) {
    return NextResponse.json(
      { ok: false, error: "Không đọc được dữ liệu siêu âm." },
      { status: 502 },
    );
  }
  return NextResponse.json({ ok: true, ...data });
}

export async function POST(request: Request) {
  if (!(await requireUser()))
    return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  const body = await request.json().catch(() => ({}));
  return proxyJsonToBackend("POST", "/api/v1/ultrasound/draft", body);
}
