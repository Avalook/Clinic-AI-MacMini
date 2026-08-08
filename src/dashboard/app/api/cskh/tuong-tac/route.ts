// Sổ tương tác CSKH — ghi lại từng lần chạm tới khách, và đọc lại nó.
//
//   GET  ?clinic_patient_id=…   → dòng thời gian của một khách
//   POST { clinic_patient_id, loai, kenh, ket_qua, … }  → ghi một lần chạm
//
// Đi qua FastAPI. Bảng chỉ mở SELECT cho client (ADR-0012): client tự ghi được
// nghĩa là client tự khai được "đã gọi rồi" cho một cuộc gọi chưa hề xảy ra.

import { NextResponse } from "next/server";
import {
  fetchFromBackend,
  proxyJsonToBackend,
} from "../../../../lib/backend-proxy";

export async function GET(request: Request) {
  const id = (
    new URL(request.url).searchParams.get("clinic_patient_id") ?? ""
  ).trim();
  if (!id) {
    return NextResponse.json({ error: "Thiếu mã khách hàng." }, { status: 400 });
  }
  const data = await fetchFromBackend<{ items: unknown[] }>(
    `/api/v1/cskh/tuong-tac/${encodeURIComponent(id)}`,
  );
  // null = không gọi được backend. Trả 503 chứ đừng trả danh sách rỗng: "chưa
  // ai gọi khách này" và "không đọc được lịch sử" là hai chuyện khác hẳn, và
  // cái thứ hai hiện thành cái thứ nhất sẽ khiến CSKH gọi lại lần thứ ba.
  if (data === null) {
    return NextResponse.json(
      { error: "Không đọc được lịch sử tương tác." },
      { status: 503 },
    );
  }
  return NextResponse.json(data);
}

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  return proxyJsonToBackend("POST", "/api/v1/cskh/tuong-tac", body);
}
