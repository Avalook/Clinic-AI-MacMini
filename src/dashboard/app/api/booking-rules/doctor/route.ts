// Luật bắt buộc bác sĩ — cấu hình của quản lý.
//
//   GET                       → mọi luật của phòng khám
//   GET ?xem_thu=1&…          → cách tính này coi bao nhiêu khách là "mới"
//   PUT  { service_type_id, required_staff_id, cach_tinh, … }
//   DELETE { id }
//
// Mọi thứ đi qua FastAPI. Bảng luật KHÔNG mở đường ghi cho client: client tự
// sửa được luật nghĩa là client tự quyết được ai phải khám ai.

import { NextResponse } from "next/server";
import {
  fetchFromBackend,
  proxyJsonToBackend,
} from "../../../../lib/backend-proxy";

export async function GET(request: Request) {
  const sp = new URL(request.url).searchParams;

  if (sp.get("xem_thu")) {
    const q = new URLSearchParams({
      service_type_id: sp.get("service_type_id") ?? "",
      cach_tinh: sp.get("cach_tinh") ?? "DOT_MOI",
    });
    const n = sp.get("so_thang");
    if (n) q.set("so_thang", n);
    const data = await fetchFromBackend<{ khach_moi: number; tong: number }>(
      `/api/v1/booking-rules/doctor/xem-thu?${q.toString()}`,
    );
    if (data === null) {
      return NextResponse.json({ error: "Không đếm được." }, { status: 503 });
    }
    return NextResponse.json(data);
  }

  const data = await fetchFromBackend<{ items: unknown[] }>(
    "/api/v1/booking-rules/doctor",
  );
  // null = không gọi được backend. Trả 503 chứ đừng trả danh sách rỗng: "chưa
  // có luật nào" và "không đọc được luật" là hai chuyện khác hẳn nhau, và cái
  // thứ hai mà hiện thành cái thứ nhất sẽ khiến quản lý tạo lại luật đã có.
  if (data === null) {
    return NextResponse.json({ error: "Không đọc được luật." }, { status: 503 });
  }
  return NextResponse.json(data);
}

export async function PUT(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  return proxyJsonToBackend("PUT", "/api/v1/booking-rules/doctor", body);
}

export async function DELETE(request: Request) {
  let body: { id?: string };
  try {
    body = (await request.json()) as { id?: string };
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const id = (body.id ?? "").trim();
  if (!id) return NextResponse.json({ error: "Thiếu id luật." }, { status: 400 });
  return proxyJsonToBackend(
    "DELETE",
    `/api/v1/booking-rules/doctor/${encodeURIComponent(id)}`,
    {},
  );
}
