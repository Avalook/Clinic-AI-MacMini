// /api/chuc-nang-phong — proxy mỏng (04/11/2026), chức năng tại chỗ của phòng.
//   GET ?room_id=                      → /api/v1/clinic-config/phong/{id}/chuc-nang
//   PUT {room_id, work_pack, bat}      → cùng đường, PUT
// Quyền do máy chủ quyết (`config.clinic.manage`); ở đây không gác thêm.
import { proxyJsonToBackend } from "../../../lib/backend-proxy";

const UUID = /^[0-9a-f-]{36}$/i;

export async function GET(request: Request) {
  const roomId = new URL(request.url).searchParams.get("room_id") ?? "";
  if (!UUID.test(roomId)) return Response.json({ error: "Thiếu mã phòng." }, { status: 400 });
  return proxyJsonToBackend("GET", `/api/v1/clinic-config/phong/${roomId}/chuc-nang`, undefined);
}

export async function PUT(request: Request) {
  const body = (await request.json().catch(() => null)) as {
    room_id?: string;
    work_pack?: string;
    bat?: boolean;
  } | null;
  if (!body?.room_id || !UUID.test(body.room_id)) {
    return Response.json({ error: "Thiếu mã phòng." }, { status: 400 });
  }
  return proxyJsonToBackend("PUT", `/api/v1/clinic-config/phong/${body.room_id}/chuc-nang`, {
    work_pack: body.work_pack,
    bat: body.bat,
  });
}
