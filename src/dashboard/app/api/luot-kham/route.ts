// Proxy màn lượt khám (lát 1) xuống FastAPI.
//
// Trang này không quyết định gì. Nó xác nhận có phiên đăng nhập, chọn đúng một
// đường backend theo DANH SÁCH TRẮNG, rồi chuyển nguyên thân và khoá gửi lại.
// Vai nào được làm gì là việc của backend (require_role + service tự gác lần
// hai) — chép luật ấy vào đây là tạo bản thứ ba chờ ngày lệch.
//
// Mã trong đường dẫn phải là UUID: chuỗi tự do nối vào URL là cách mở một đường
// backend không nằm trong danh sách.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { proxyJsonToBackend } from "../../../lib/backend-proxy";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Thao tác cho phép → đường backend. */
const THAO_TAC: Record<string, (id: string) => string> = {
  "check-in": () => "/api/v1/luot-kham/check-in",
  "sinh-hieu": (id) => `/api/v1/luot-kham/visits/${id}/vitals`,
  "goi-do": (id) => `/api/v1/luot-kham/visits/${id}/goi-do`,
  "nhan-kham": (id) => `/api/v1/luot-kham/consultations/${id}/start`,
  "ghi-chu": (id) => `/api/v1/luot-kham/consultations/${id}/notes`,
  "nhap-chi-dinh": (id) =>
    `/api/v1/luot-kham/consultations/${id}/draft-orders`,
  "duyet-chi-dinh": (id) =>
    `/api/v1/luot-kham/consultations/${id}/authorize-orders`,
  "ket-thuc-kham": (id) => `/api/v1/luot-kham/consultations/${id}/complete`,
  "xep-phong": (id) => `/api/v1/luot-kham/orders/${id}/dispatch`,
  "bat-dau-dich-vu": (id) => `/api/v1/luot-kham/orders/${id}/start`,
  "xong-dich-vu": (id) => `/api/v1/luot-kham/orders/${id}/complete`,
  // Nút "Đã khám xong" — máy chủ tự chọn kết quả phiên theo chỉ định còn lại.
  "kham-xong": (id) => `/api/v1/luot-kham/consultations/${id}/kham-xong`,
  "duyet-ket-qua": (id) => `/api/v1/luot-kham/orders/${id}/duyet-ket-qua`,
  // Gọi khách vào phòng — id là CHỖ CHỜ (queue entry), không phải phiên/chỉ định.
  "goi-khach": (id) => `/api/v1/luot-kham/hang-cho/${id}/goi`,
  // Bác sĩ miễn / chuyển theo dõi một yêu cầu của vòng đọc (Slice 1) — id là
  // YÊU CẦU (round_requirement).
  "quyet-yeu-cau": (id) => `/api/v1/luot-kham/yeu-cau/${id}/quyet`,
  // Khách xác nhận dịch vụ sẽ làm (Lifecycle v1, ConfirmServiceSelection) —
  // id là LƯỢT KHÁM. Khoá gửi lại là bắt buộc; backend từ chối nếu thiếu.
  "chon-dich-vu": (id) =>
    `/api/v1/luot-kham/visits/${id}/service-selection/confirm`,
};

/** Các bảng đọc — `?xem=` → đường backend. Không có `xem` = bảng lượt khám. */
function duongDoc(url: URL): string | null {
  const xem = url.searchParams.get("xem");
  if (!xem) return "/api/v1/luot-kham/bang";
  if (xem === "phong-hom-nay") return "/api/v1/luot-kham/phong-hom-nay";
  if (xem === "ket-qua-cho-duyet") return "/api/v1/luot-kham/ket-qua-cho-duyet";
  if (xem === "cho-quyet") return "/api/v1/luot-kham/cho-quyet";
  // Xem lại một lượt (chỉ đọc, backend cắt theo vai) — batch pilot 18/09.
  if (xem === "xem-luot") {
    const luot = url.searchParams.get("luot") ?? "";
    return UUID_RE.test(luot) ? `/api/v1/xem-luot/${luot}` : null;
  }
  if (xem === "chi-dinh-hom-nay") return "/api/v1/luot-kham/chi-dinh-hom-nay";
  if (xem === "hang-cho") {
    const phong = url.searchParams.get("phong") ?? "";
    if (phong && !UUID_RE.test(phong)) return null;
    return phong
      ? `/api/v1/luot-kham/hang-cho?phong=${encodeURIComponent(phong)}`
      : "/api/v1/luot-kham/hang-cho";
  }
  return null;
}

/** Thao tác không gắn với một dòng cụ thể trên đường dẫn. */
const KHONG_CAN_ID = new Set(["check-in"]);

async function coPhien(): Promise<boolean> {
  const supabase = await getSupabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  return Boolean(user);
}

export async function GET(request: Request) {
  if (!(await coPhien())) {
    return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  }
  const duong = duongDoc(new URL(request.url));
  if (!duong) {
    return NextResponse.json(
      { error: "BAD_REQUEST", message: "Bảng cần đọc không hợp lệ." },
      { status: 400 },
    );
  }
  return proxyJsonToBackend("GET", duong, undefined);
}

export async function POST(request: Request) {
  if (!(await coPhien())) {
    return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  }

  let than: { thao_tac?: unknown; id?: unknown; du_lieu?: unknown };
  try {
    than = await request.json();
  } catch {
    return NextResponse.json(
      { error: "BAD_REQUEST", message: "Dữ liệu gửi lên không đọc được." },
      { status: 400 },
    );
  }

  const tenThaoTac = typeof than.thao_tac === "string" ? than.thao_tac : "";
  const duong = THAO_TAC[tenThaoTac];
  if (!duong) {
    return NextResponse.json(
      { error: "BAD_REQUEST", message: "Thao tác không hợp lệ." },
      { status: 400 },
    );
  }
  const id = typeof than.id === "string" ? than.id : "";
  if (!KHONG_CAN_ID.has(tenThaoTac) && !UUID_RE.test(id)) {
    return NextResponse.json(
      { error: "BAD_REQUEST", message: "Mã không hợp lệ." },
      { status: 400 },
    );
  }

  const khoa = request.headers.get("Idempotency-Key") ?? undefined;
  return proxyJsonToBackend("POST", duong(id), than.du_lieu ?? {}, khoa);
}
