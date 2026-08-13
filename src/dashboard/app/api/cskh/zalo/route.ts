// Gửi tin Zalo (ZNS) cho khách.
//
//   GET   → Zalo đã đủ cấu hình chưa, và thiếu gì
//   POST  { clinic_patient_id, loai_tin[, appointment_id] } → gửi thật
//
// Đi qua FastAPI: access token của Official Account KHÔNG được xuống trình
// duyệt. Một token ZNS lộ ra là bất kỳ ai cũng gửi được tin đứng tên phòng
// khám, tới bất kỳ số nào.

import { NextResponse } from "next/server";
import {
  fetchFromBackend,
  proxyJsonToBackend,
} from "../../../../lib/backend-proxy";

export async function GET() {
  const data = await fetchFromBackend<{ bat: boolean; thieu: string[] }>(
    "/api/v1/cskh/zalo/trang-thai",
  );
  // Không đọc được thì coi như CHƯA BẬT. Đoán "bật" khi không biết là mời
  // người dùng bấm một nút chắc chắn hỏng.
  if (data === null) {
    return NextResponse.json({ bat: false, thieu: ["không đọc được cấu hình"] });
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
  return proxyJsonToBackend("POST", "/api/v1/cskh/zalo/gui", body);
}
