// Các bước ghi của một phiếu kiểm kê ca (G6) → FastAPI. Danh sách trắng: một
// `[buoc]` trần sẽ mở luôn cả đường thêm sau này mà chưa ai cân nhắc.
//   dem · dung-so-cuoi-ca-truoc · chot (số đếm thành tồn thật ngay) ·
//   dieu-chinh (phiếu cũ chưa ghi sổ) · hoan-tac-dieu-chinh

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../../../../lib/supabase-server";
import { proxyJsonToBackend } from "../../../../../../lib/backend-proxy";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const BUOC = new Set(["dem", "dung-so-cuoi-ca-truoc", "chot", "dieu-chinh", "hoan-tac-dieu-chinh", "sua-so-dem"]);

/** Chỉ đọc: dòng nào lệch trước khi chốt, để màn hỏi lý do từng dòng. */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string; buoc: string }> },
) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  const { id, buoc } = await params;
  if (!UUID_RE.test(id) || buoc !== "xem-lech") {
    return NextResponse.json({ error: `Không đọc được: ${buoc}` }, { status: 400 });
  }
  return proxyJsonToBackend("GET", `/api/v1/pharmacy/kiem-ke-ca/${id}/xem-lech`, undefined);
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string; buoc: string }> },
) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  const { id, buoc } = await params;
  if (!UUID_RE.test(id) || !BUOC.has(buoc)) {
    return NextResponse.json({ error: `Thao tác không hợp lệ: ${buoc}` }, { status: 400 });
  }
  // Các bước không có thân (chốt, dùng số cuối ca trước, hoàn tác) gửi `{}`.
  const body: unknown = await request.json().catch(() => ({}));
  return proxyJsonToBackend("POST", `/api/v1/pharmacy/kiem-ke-ca/${id}/${buoc}`, body);
}
