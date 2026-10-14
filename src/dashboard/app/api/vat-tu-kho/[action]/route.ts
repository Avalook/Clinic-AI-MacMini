// Proxy Kho vật tư xuống FastAPI (G8a, 14/10/2026) — chỉ chuyển tiếp.
//
// Quyền (`vat_tu.manage`, lego "Kho vật tư") và mọi luật (tồn âm vẫn xuất được,
// số rác 422, phiếu đảo một lần) do máy chủ quyết; ở đây chỉ kiểm đăng nhập và
// HÌNH của tham số. Danh sách trắng: đường thêm sau này không tự mở ra trình duyệt.

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "../../../../lib/backend-proxy";
import { getSupabaseServer } from "../../../../lib/supabase-server";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Đường ĐỌC cho phép → đường backend. */
const DOC: Record<string, (q: URLSearchParams) => string> = {
  ton: () => "/api/v1/vat-tu-kho/ton",
  "canh-bao": () => "/api/v1/vat-tu-kho/canh-bao",
  "tieu-hao": (q) =>
    `/api/v1/vat-tu-kho/tieu-hao?${new URLSearchParams({
      ky: q.get("ky") ?? "",
      tu: q.get("tu") ?? "",
      den: q.get("den") ?? "",
    })}`,
  phieu: (q) => `/api/v1/vat-tu-kho/phieu?${new URLSearchParams({ gioi_han: q.get("gioi_han") ?? "" })}`,
};

async function daDangNhap(): Promise<NextResponse | null> {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  return user ? null : NextResponse.json({ error: "Unauthorised" }, { status: 401 });
}

async function docBody(request: Request): Promise<{ body: unknown } | NextResponse> {
  try {
    return { body: await request.json() };
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
}

export async function GET(request: Request, { params }: { params: Promise<{ action: string }> }) {
  const chan = await daDangNhap();
  if (chan) return chan;
  const { action } = await params;
  const tao = DOC[action];
  if (!tao) return NextResponse.json({ error: `Không đọc được: ${action}` }, { status: 400 });
  return proxyJsonToBackend("GET", tao(new URL(request.url).searchParams), undefined);
}

export async function POST(request: Request, { params }: { params: Promise<{ action: string }> }) {
  const chan = await daDangNhap();
  if (chan) return chan;
  const { action } = await params;
  if (action !== "phieu" && action !== "hoan") {
    return NextResponse.json({ error: `Thao tác không hợp lệ: ${action}` }, { status: 400 });
  }
  const goi = await docBody(request);
  if (goi instanceof NextResponse) return goi;
  // Khoá chống gửi trùng: lập phiếu / đảo phiếu bắt buộc, máy chủ từ chối khi thiếu.
  const khoa = request.headers.get("Idempotency-Key") ?? undefined;
  if (action === "phieu") return proxyJsonToBackend("POST", "/api/v1/vat-tu-kho/phieu", goi.body, khoa);
  const b = (goi.body ?? {}) as { phieu_id?: unknown; ghi_chu?: unknown };
  if (typeof b.phieu_id !== "string" || !UUID_RE.test(b.phieu_id)) {
    return NextResponse.json({ error: "Mã phiếu không hợp lệ." }, { status: 400 });
  }
  return proxyJsonToBackend(
    "POST",
    `/api/v1/vat-tu-kho/phieu/${b.phieu_id}/hoan`,
    { ghi_chu: typeof b.ghi_chu === "string" ? b.ghi_chu : null },
    khoa,
  );
}

export async function PUT(request: Request, { params }: { params: Promise<{ action: string }> }) {
  const chan = await daDangNhap();
  if (chan) return chan;
  const { action } = await params;
  if (action !== "muc-toi-thieu") {
    return NextResponse.json({ error: `Thao tác không hợp lệ: ${action}` }, { status: 400 });
  }
  const goi = await docBody(request);
  if (goi instanceof NextResponse) return goi;
  return proxyJsonToBackend("PUT", "/api/v1/vat-tu-kho/muc-toi-thieu", goi.body);
}
