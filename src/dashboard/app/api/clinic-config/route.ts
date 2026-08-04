// Cấu hình phòng khám — chỉ chuyển tiếp xuống FastAPI.
//
// Không có luật nào ở đây, kể cả luật quyền. `assert_may_configure` ở
// clinic_config_service là chốt thật; thêm một lần kiểm vai ở đây sẽ tạo hai
// nơi trả lời cùng một câu hỏi, và nơi bị quên là nơi mở.
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

  const what = new URL(request.url).searchParams.get("what") ?? "overview";
  const data = await fetchFromBackend<Record<string, unknown>>(
    what === "staff"
      ? "/api/v1/clinic-config/staff"
      : "/api/v1/clinic-config/overview",
  );
  if (data === null) {
    return NextResponse.json(
      { ok: false, error: "Không đọc được cấu hình phòng khám." },
      { status: 502 },
    );
  }
  return NextResponse.json({ ok: true, ...data });
}

// Ba việc ghi đi chung một cửa, phân theo `what`. Backend vẫn là ba đường riêng
// với ba hình dạng riêng — gộp ở đây chỉ để màn hình không phải nhớ ba URL.
const WRITE_PATHS: Record<string, string> = {
  "room-floor": "/api/v1/clinic-config/room-floor",
  "room-nodes": "/api/v1/clinic-config/room-nodes",
  "staff-nodes": "/api/v1/clinic-config/staff-nodes",
};

export async function PUT(request: Request) {
  if (!(await requireUser()))
    return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  const body = (await request.json().catch(() => ({}))) as Record<
    string,
    unknown
  >;
  const { what, ...payload } = body;
  const path = WRITE_PATHS[String(what ?? "")];
  if (!path) {
    return NextResponse.json(
      { ok: false, error: `Không rõ cần sửa gì: ${String(what)}` },
      { status: 400 },
    );
  }
  return proxyJsonToBackend("PUT", path, payload);
}
