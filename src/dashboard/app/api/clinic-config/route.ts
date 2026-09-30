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

  const url = new URL(request.url);
  const what = url.searchParams.get("what") ?? "overview";
  const tuan = (url.searchParams.get("tuan") ?? "").slice(0, 10);
  // Rác / rỗng → máy chủ tự hiểu là tuần này (`lich_phong_service.doc_tuan`).
  const tuanHopLe = /^\d{4}-\d{2}-\d{2}$/.test(tuan) ? tuan : "";
  const data = await fetchFromBackend<Record<string, unknown>>(
    what === "staff"
      ? "/api/v1/clinic-config/staff"
      : what === "lich-phong"
        ? `/api/v1/clinic-config/lich-phong?tuan=${tuanHopLe}`
      : what === "services"
        ? "/api/v1/clinic-config/services"
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
  // Phòng là tài nguyên (23/09/2026): đổi tên / bật-tắt theo room_id.
  "room-name": "/api/v1/clinic-config/room-name",
  "room-active": "/api/v1/clinic-config/room-active",
  "room-nodes": "/api/v1/clinic-config/room-nodes",
  // Dịch vụ lẻ của phòng — dịch vụ gắn ở đây chỉ làm ở phòng được gắn (30/09/2026).
  "room-services": "/api/v1/clinic-config/room-services",
  "staff-nodes": "/api/v1/clinic-config/staff-nodes",
  "service-form": "/api/v1/clinic-config/service-form",
  "service-type": "/api/v1/clinic-config/service-type",
  // Thư ký đi cùng bác sĩ nào (Tuyền chốt 15/09/2026).
  "thu-ky-bac-si": "/api/v1/clinic-config/thu-ky-bac-si",
  // Cơ sở (27/09/2026, màn Cấu trúc phòng khám làm lại).
  location: "/api/v1/clinic-config/location",
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

// Thêm phòng (23/09/2026) — POST vì tạo mới; backend tự sinh mã nội bộ.
export async function POST(request: Request) {
  if (!(await requireUser()))
    return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  const body = (await request.json().catch(() => ({}))) as Record<string, unknown>;
  const { what, ...payload } = body;
  if (what === "location-create") {
    return proxyJsonToBackend("POST", "/api/v1/clinic-config/locations", payload);
  }
  if (what !== "room-create") {
    return NextResponse.json(
      { ok: false, error: `Không rõ cần tạo gì: ${String(what)}` },
      { status: 400 },
    );
  }
  return proxyJsonToBackend("POST", "/api/v1/clinic-config/rooms", payload);
}
