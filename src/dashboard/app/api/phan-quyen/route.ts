// Phân quyền — proxy mỏng sang FastAPI.
//
//   GET  /api/phan-quyen                     → danh mục khối + quyền + preset
//   GET  /api/phan-quyen?staff=<uuid>        → người này đang có khối nào
//   GET  /api/phan-quyen?lego=<uuid>         → 21 lego của người này (25/09)
//   GET  /api/phan-quyen?nhom=1              → nhóm quyền mẫu của phòng khám
//   POST /api/phan-quyen                     → { thao_tac, staff_id, ... }
//
// Ba thao tác không gắn với một người mà gắn với NHÓM MẪU (`luu-nhom`,
// `xoa-nhom`): quản lý tự thêm/sửa/xoá nhóm, không cần ai deploy.
//
// Không chép luật quyền sang đây. Ai được cấp quyền cho ai là capability
// `permission.manage`, kiểm trong service và trong chính giao dịch của lệnh —
// một bản sao ở tầng này là một bản sao sẽ lệch.

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "../../../lib/backend-proxy";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Thao tác cho phép → đường backend. */
const THAO_TAC: Record<string, (id: string) => string> = {
  cap: (id) => `/api/v1/phan-quyen/nhan-su/${id}/cap`,
  thu: (id) => `/api/v1/phan-quyen/nhan-su/${id}/thu`,
  "them-preset": (id) => `/api/v1/phan-quyen/nhan-su/${id}/them-preset`,
  // 21 lego theo node thanh bên (25/09/2026): bật / tắt một lego.
  "doi-lego": (id) => `/api/v1/phan-quyen/nhan-su/${id}/lego`,
};

export async function GET(request: Request) {
  const q = new URL(request.url).searchParams;
  if (q.get("nhom") !== null) {
    return proxyJsonToBackend("GET", "/api/v1/phan-quyen/nhom", undefined);
  }
  // Quyền THEO MÀN (Tuyền chốt 23/09): nhóm mẫu nào đang bật màn nào.
  if (q.get("man") !== null) {
    return proxyJsonToBackend("GET", "/api/v1/phan-quyen/man", undefined);
  }
  // Lego của một người (25/09/2026).
  const lego = q.get("lego");
  if (lego !== null) {
    if (!UUID_RE.test(lego)) {
      return NextResponse.json(
        { error: "BAD_REQUEST", message: "Mã nhân sự không hợp lệ." },
        { status: 400 },
      );
    }
    return proxyJsonToBackend("GET", `/api/v1/phan-quyen/nhan-su/${lego}/lego`, undefined);
  }
  const staff = q.get("staff");
  if (staff === null) {
    return proxyJsonToBackend("GET", "/api/v1/phan-quyen/danh-muc", undefined);
  }
  if (!UUID_RE.test(staff)) {
    return NextResponse.json(
      { error: "BAD_REQUEST", message: "Mã nhân sự không hợp lệ." },
      { status: 400 },
    );
  }
  return proxyJsonToBackend(
    "GET",
    `/api/v1/phan-quyen/nhan-su/${staff}`,
    undefined,
  );
}

export async function POST(request: Request) {
  let than: {
    thao_tac?: unknown;
    staff_id?: unknown;
    ma?: unknown;
    du_lieu?: unknown;
  };
  try {
    than = await request.json();
  } catch {
    return NextResponse.json(
      { error: "BAD_REQUEST", message: "Dữ liệu gửi lên không đọc được." },
      { status: 400 },
    );
  }
  const ten = typeof than.thao_tac === "string" ? than.thao_tac : "";

  // Nhóm quyền mẫu: mã nhóm do người đặt nên KHÔNG phải UUID — kiểm hình dạng
  // chặt ở đây để một chuỗi tự do không nối được vào URL backend.
  if (ten === "doi-man") {
    return proxyJsonToBackend("POST", "/api/v1/phan-quyen/man", than.du_lieu ?? {});
  }
  if (ten === "luu-nhom") {
    return proxyJsonToBackend("POST", "/api/v1/phan-quyen/nhom", than.du_lieu ?? {});
  }
  if (ten === "xoa-nhom") {
    const ma = typeof than.ma === "string" ? than.ma : "";
    if (!/^[A-Za-z0-9_]{2,32}$/.test(ma)) {
      return NextResponse.json(
        { error: "BAD_REQUEST", message: "Mã nhóm không hợp lệ." },
        { status: 400 },
      );
    }
    return proxyJsonToBackend(
      "POST",
      `/api/v1/phan-quyen/nhom/${ma}/xoa`,
      {},
    );
  }

  const duong = THAO_TAC[ten];
  const id = typeof than.staff_id === "string" ? than.staff_id : "";
  if (!duong || !UUID_RE.test(id)) {
    return NextResponse.json(
      { error: "BAD_REQUEST", message: "Thao tác hoặc mã nhân sự không hợp lệ." },
      { status: 400 },
    );
  }
  return proxyJsonToBackend("POST", duong(id), than.du_lieu ?? {});
}
