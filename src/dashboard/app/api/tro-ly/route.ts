// /api/tro-ly — proxy mỏng cho màn thử trợ lý AI (/tro-ly-thu).
//   GET ?xem=trang-thai                 → /api/v1/tro-ly/trang-thai
//   GET ?xem=hoi-thoai                  → /api/v1/tro-ly/hoi-thoai
//   GET ?xem=hoi-thoai&id=…             → /api/v1/tro-ly/hoi-thoai/{id}
//   POST {viec:"tao", tieu_de?}         → /api/v1/tro-ly/hoi-thoai
//   POST {viec:"gui", id, noi_dung, mo_hinh?} → /api/v1/tro-ly/hoi-thoai/{id}/tin
//   POST {viec:"duyet", tin_id, hanh_dong, noi_dung?} → /api/v1/tro-ly/tin/{id}/duyet
// Quyền (`ops.view`) và cờ bật do máy chủ quyết; ở đây chỉ kiểm HÌNH của mã.
import { proxyJsonToBackend } from "../../../lib/backend-proxy";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(request: Request) {
  const u = new URL(request.url);
  const xem = u.searchParams.get("xem");
  if (xem === "trang-thai") {
    return proxyJsonToBackend("GET", "/api/v1/tro-ly/trang-thai", undefined);
  }
  if (xem === "hoi-thoai") {
    const id = u.searchParams.get("id");
    if (!id) return proxyJsonToBackend("GET", "/api/v1/tro-ly/hoi-thoai", undefined);
    if (!UUID_RE.test(id)) return Response.json({ error: "Mã hội thoại sai." }, { status: 400 });
    return proxyJsonToBackend("GET", `/api/v1/tro-ly/hoi-thoai/${id}`, undefined);
  }
  return Response.json({ error: "Thiếu ?xem=trang-thai|hoi-thoai" }, { status: 400 });
}

export async function POST(request: Request) {
  const b = (await request.json().catch(() => null)) as Record<string, unknown> | null;
  const viec = b?.viec;
  if (viec === "tao") {
    return proxyJsonToBackend("POST", "/api/v1/tro-ly/hoi-thoai", {
      tieu_de: typeof b?.tieu_de === "string" ? b.tieu_de : null,
    });
  }
  if (viec === "gui") {
    if (typeof b?.id !== "string" || !UUID_RE.test(b.id)) {
      return Response.json({ error: "Mã hội thoại sai." }, { status: 400 });
    }
    return proxyJsonToBackend("POST", `/api/v1/tro-ly/hoi-thoai/${b.id}/tin`, {
      noi_dung: b.noi_dung,
      mo_hinh: b.mo_hinh ?? null,
    });
  }
  if (viec === "duyet") {
    if (typeof b?.tin_id !== "string" || !UUID_RE.test(b.tin_id)) {
      return Response.json({ error: "Mã tin sai." }, { status: 400 });
    }
    return proxyJsonToBackend("POST", `/api/v1/tro-ly/tin/${b.tin_id}/duyet`, {
      hanh_dong: b.hanh_dong,
      noi_dung: b.noi_dung ?? null,
    });
  }
  return Response.json({ error: "Thiếu viec=tao|gui|duyet" }, { status: 400 });
}
