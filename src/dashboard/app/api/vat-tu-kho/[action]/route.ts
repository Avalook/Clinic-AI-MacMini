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
  // G8b: yêu cầu nhập chờ duyệt (+ đã quyết gần đây, `duoc_duyet`, `cua_toi`).
  "cho-duyet": () => "/api/v1/vat-tu-kho/cho-duyet",
  phieu: (q) =>
    `/api/v1/vat-tu-kho/phieu?${new URLSearchParams({
      gioi_han: q.get("gioi_han") ?? "",
      bo_qua: q.get("bo_qua") ?? "",
      vat_tu_id: q.get("vat_tu_id") ?? "",
    })}`,
  ban: (q) =>
    `/api/v1/vat-tu-kho/ban?${new URLSearchParams({
      tu: q.get("tu") ?? "",
      den: q.get("den") ?? "",
      noi: q.get("noi") ?? "",
      trang_thai: q.get("trang_thai") ?? "",
    })}`,
  "ban-tim-khach": (q) => `/api/v1/vat-tu-kho/ban/tim-khach?${new URLSearchParams({ q: q.get("q") ?? "" })}`,
};

/** Lệnh trên một dòng bán → đuôi đường backend. Mọi luật ở máy chủ. */
const LENH_BAN: Record<string, string> = {
  "ban-gan-phong": "gan-phong",
  "ban-nhan-lai": "nhan-lai",
  "ban-khong-nhan-lai": "khong-nhan-lai",
  "ban-hoan-tac": "hoan-tac",
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

/** Lệnh quyết yêu cầu nhập chờ duyệt (G8b) → đuôi đường backend. Quyền (Duyệt vật tư /
 *  Kho vật tư), lý do 5–500 ký tự, "chỉ quyết một lần" do MÁY CHỦ quyết. */
const QUYET_NHAP: Record<string, string> = {
  "nhap-duyet": "duyet",
  "nhap-tu-choi": "tu-choi",
  "nhap-rut-lai": "rut-lai",
};

export async function POST(request: Request, { params }: { params: Promise<{ action: string }> }) {
  const chan = await daDangNhap();
  if (chan) return chan;
  const { action } = await params;
  if (action !== "phieu" && action !== "hoan" && action !== "ban-nhap-bu" && !(action in QUYET_NHAP) && !(action in LENH_BAN)) {
    return NextResponse.json({ error: `Thao tác không hợp lệ: ${action}` }, { status: 400 });
  }
  const goi = await docBody(request);
  if (goi instanceof NextResponse) return goi;
  if (action === "ban-nhap-bu") {
    return proxyJsonToBackend("POST", "/api/v1/vat-tu-kho/ban/nhap-bu", goi.body, request.headers.get("Idempotency-Key") ?? undefined);
  }
  if (action in LENH_BAN) {
    const { ban_id: banId, ...conLai } = (goi.body ?? {}) as { ban_id?: unknown } & Record<string, unknown>;
    if (typeof banId !== "string" || !UUID_RE.test(banId)) {
      return NextResponse.json({ error: "Mã dòng bán không hợp lệ." }, { status: 400 });
    }
    return proxyJsonToBackend(
      "POST",
      `/api/v1/vat-tu-kho/ban/${banId}/${LENH_BAN[action]}`,
      conLai,
      request.headers.get("Idempotency-Key") ?? undefined,
    );
  }
  if (action in QUYET_NHAP) {
    const q = (goi.body ?? {}) as { yeu_cau_id?: unknown; ly_do?: unknown };
    if (typeof q.yeu_cau_id !== "string" || !UUID_RE.test(q.yeu_cau_id)) {
      return NextResponse.json({ error: "Mã yêu cầu không hợp lệ." }, { status: 400 });
    }
    // Lý do đi nguyên văn (kể cả rỗng / rác) để máy chủ trả 422 có lời; duyệt không cần lý do.
    return proxyJsonToBackend(
      "POST",
      `/api/v1/vat-tu-kho/cho-duyet/${q.yeu_cau_id}/${QUYET_NHAP[action]}`,
      action === "nhap-duyet" ? undefined : { ly_do: q.ly_do ?? null },
    );
  }
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
