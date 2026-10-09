// /api/ops/agent — proxy mỏng sang agent giám sát (09/10/2026, shadow).
//   GET [?chi_mo=1]                                      → /api/v1/ops/agent
//   POST {hanh_dong:"danh-gia", id, danh_gia, ghi_chu}   → /api/v1/ops/agent/{id}/danh-gia
//   POST {hanh_dong:"che-do", loai, che_do}              → /api/v1/ops/agent/che-do
// Quyền do máy chủ quyết (lego Vận hành — `ops.view`); ở đây không gác thêm.
import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

//   GET ?xem=tom-tat[&ngay=YYYY-MM-DD]               → /api/v1/ops/agent/tom-tat
//   GET ?xem=chi-phi[&so_ngay=N]                     → /api/v1/ops/llm/chi-phi
//   POST {hanh_dong:"tom-tat", ngay?}                → /api/v1/ops/agent/tom-tat
export async function GET(request: Request) {
  const u = new URL(request.url);
  const xem = u.searchParams.get("xem");
  if (xem === "tom-tat") {
    const ngay = u.searchParams.get("ngay");
    return proxyJsonToBackend(
      "GET",
      ngay ? `/api/v1/ops/agent/tom-tat?ngay=${encodeURIComponent(ngay)}` : "/api/v1/ops/agent/tom-tat",
      undefined,
    );
  }
  if (xem === "chi-phi") {
    const n = Number(u.searchParams.get("so_ngay"));
    const soNgay = Number.isInteger(n) && n >= 1 && n <= 31 ? n : 7;
    return proxyJsonToBackend("GET", `/api/v1/ops/llm/chi-phi?so_ngay=${soNgay}`, undefined);
  }
  return proxyJsonToBackend(
    "GET",
    u.searchParams.get("chi_mo") === "1" ? "/api/v1/ops/agent?chi_mo=true" : "/api/v1/ops/agent",
    undefined,
  );
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as {
    hanh_dong?: string;
    id?: string;
    danh_gia?: string | null;
    ghi_chu?: string | null;
    loai?: string;
    che_do?: string;
  } | null;
  if (body?.hanh_dong === "danh-gia") {
    if (!body.id || !/^[0-9a-f-]{36}$/i.test(body.id)) {
      return Response.json({ error: "Thiếu mã nhận định." }, { status: 400 });
    }
    return proxyJsonToBackend("POST", `/api/v1/ops/agent/${body.id}/danh-gia`, {
      danh_gia: body.danh_gia ?? null,
      ghi_chu: body.ghi_chu ?? null,
    });
  }
  if (body?.hanh_dong === "tom-tat") {
    return proxyJsonToBackend("POST", "/api/v1/ops/agent/tom-tat", {
      ngay: (body as { ngay?: string | null }).ngay ?? null,
    });
  }
  if (body?.hanh_dong === "che-do") {
    return proxyJsonToBackend("POST", "/api/v1/ops/agent/che-do", {
      loai: body.loai,
      che_do: body.che_do,
    });
  }
  return Response.json({ error: "Thiếu hanh_dong=danh-gia|che-do" }, { status: 400 });
}
