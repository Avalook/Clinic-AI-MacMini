// /api/ops/theo-doi — proxy mỏng sang theo dõi lỗi Pha 1 (27/09/2026).
//   GET ?xem=loi[&chi_mo=1]        → /api/v1/ops/loi        (kiểu lỗi đã gom)
//   GET ?xem=canh-bao              → /api/v1/ops/canh-bao   (bộ canh gác)
//   GET ?xem=nhat-ky[&ngay&tim]    → /api/v1/ops/nhat-ky    (ai làm gì, bao lâu)
//   POST {loi_id, trang_thai}      → /api/v1/ops/loi/{id}/trang-thai
// Quyền do máy chủ quyết (lego Vận hành — `ops.view`); ở đây không gác thêm.
import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

export async function GET(request: Request) {
  const u = new URL(request.url);
  const xem = u.searchParams.get("xem");
  if (xem === "loi") {
    const chiMo = u.searchParams.get("chi_mo") === "1" ? "?chi_mo=true" : "";
    return proxyJsonToBackend("GET", `/api/v1/ops/loi${chiMo}`, undefined);
  }
  if (xem === "canh-bao") return proxyJsonToBackend("GET", "/api/v1/ops/canh-bao", undefined);
  if (xem === "nhat-ky") {
    const q = new URLSearchParams();
    for (const k of ["ngay", "tim"]) {
      const v = u.searchParams.get(k);
      if (v) q.set(k, v);
    }
    return proxyJsonToBackend("GET", `/api/v1/ops/nhat-ky?${q.toString()}`, undefined);
  }
  return Response.json({ error: "Thiếu ?xem=loi|canh-bao|nhat-ky" }, { status: 400 });
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as {
    loi_id?: string;
    trang_thai?: string;
  } | null;
  if (!body?.loi_id || !/^[0-9a-f-]{36}$/i.test(body.loi_id)) {
    return Response.json({ error: "Thiếu mã lỗi." }, { status: 400 });
  }
  return proxyJsonToBackend("POST", `/api/v1/ops/loi/${body.loi_id}/trang-thai`, {
    trang_thai: body.trang_thai,
  });
}
