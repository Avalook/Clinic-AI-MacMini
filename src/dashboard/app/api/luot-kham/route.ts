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
};

/** Thao tác không gắn với một dòng cụ thể trên đường dẫn. */
const KHONG_CAN_ID = new Set(["check-in"]);

async function coPhien(): Promise<boolean> {
  const supabase = await getSupabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  return Boolean(user);
}

export async function GET() {
  if (!(await coPhien())) {
    return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  }
  return proxyJsonToBackend("GET", "/api/v1/luot-kham/bang", undefined);
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
