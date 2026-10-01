// Đóng lượt khám — proxy xuống FastAPI.
//
// Đóng lượt KHÔNG đụng `visit.status`: đó là khoá hồ sơ bệnh án theo
// TT13/2011/TT-BYT. Toàn bộ luật nằm ở checkout_service.py; route này chỉ
// chuyển tiếp; backend gác quyền.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../../lib/supabase-server";
import { proxyJsonToBackend, fetchFromBackend } from "../../../../lib/backend-proxy";

async function guard() {
  const supabase = await getSupabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return "Chưa đăng nhập";
  // Quyền đóng lượt là việc của BACKEND (reception.checkin.perform — lego Tiếp
  // đón khách). Cửa vai cũ ở đây chặn người đã được cấp lego (27/09/2026).
  return null;
}

export async function GET(request: Request) {
  const err = await guard();
  if (err) return NextResponse.json({ error: err }, { status: 403 });

  // Bốn dạng: danh sách hôm nay · điều kiện đóng của một lượt · TOÀN CẢNH một
  // lượt (dịch vụ, tiền, hồ sơ, theo dõi, dòng thời gian) để Lễ tân đối soát ·
  // LƯỢT TỒN ĐỌNG từ hôm trước (`?ton_dong=1`, đợt 3 27/09/2026 — API có sẵn từ
  // 06/08 mà chưa màn nào đọc).
  const params = new URL(request.url).searchParams;
  const visit = params.get("visit_id");
  const chiTiet = params.get("chi_tiet") === "1";
  const tonDong = params.get("ton_dong") === "1";
  let duong = "/api/v1/reception/checkout";
  if (tonDong) duong = "/api/v1/reception/checkout/ton-dong";
  else if (visit && chiTiet)
    duong = `/api/v1/reception/checkout/chi-tiet/${encodeURIComponent(visit)}`;
  else if (visit) duong = `/api/v1/reception/checkout/${encodeURIComponent(visit)}`;
  const data = await fetchFromBackend<unknown>(duong);
  // `null` = backend im lặng. Trả ok:false để màn hình nói ra, thay vì vẽ một
  // danh sách rỗng trông y hệt "hôm nay không còn ai cần đóng".
  return NextResponse.json(data ?? { ok: false });
}

export async function POST(request: Request) {
  const err = await guard();
  if (err) return NextResponse.json({ error: err }, { status: 403 });

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  // GHI NỢ / HUỶ GHI NỢ (01/10/2026): khách về khi còn nợ. Cùng cửa với
  // check-out; máy chủ quyết mọi thứ (`cong_no_service`).
  const hanhDong =
    body && typeof body === "object" ? (body as { hanh_dong?: unknown }).hanh_dong : null;
  if (hanhDong === "ghi_no" || hanhDong === "huy_ghi_no") {
    const { visit_id, ly_do } = body as { visit_id?: unknown; ly_do?: unknown };
    return proxyJsonToBackend(
      "POST",
      hanhDong === "ghi_no"
        ? "/api/v1/reception/checkout/ghi-no"
        : "/api/v1/reception/checkout/huy-ghi-no",
      { visit_id, ly_do },
    );
  }
  return proxyJsonToBackend("POST", "/api/v1/reception/checkout", body);
}
