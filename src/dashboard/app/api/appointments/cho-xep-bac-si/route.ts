// Hàng chờ xếp bác sĩ.
//
//   GET                      → lịch đã đặt mà chưa có bác sĩ
//   POST { appointment_id }  → CSKH báo quản lý rằng lịch này cần xếp người
//
// Đường RIÊNG chứ không nhét vào /api/appointments: cửa PATCH ở đó là vòng đời
// một lịch hẹn, còn hai việc này là một HÀNG ĐỢI và một lời nhắn. Gộp lại thì
// danh sách trắng action ở đó phải mở rộng cho hai thứ không phải chuyển tiếp.

import { NextResponse } from "next/server";
import {
  fetchFromBackend,
  proxyJsonToBackend,
} from "../../../../lib/backend-proxy";

export async function GET() {
  const data = await fetchFromBackend<{ items: unknown[] }>(
    "/api/v1/appointments/cho-xep-bac-si",
  );
  // `null` = không gọi được backend. Trả 503 chứ đừng trả danh sách rỗng: một
  // hàng chờ rỗng vì hỏng trông y hệt một hàng chờ rỗng vì đã xếp xong hết.
  if (data === null) {
    return NextResponse.json(
      { error: "Không đọc được hàng chờ." },
      { status: 503 },
    );
  }
  return NextResponse.json(data);
}

interface PostBody {
  appointment_id?: string;
  ghi_chu?: string;
}

export async function POST(request: Request) {
  let body: PostBody;
  try {
    body = (await request.json()) as PostBody;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const id = (body.appointment_id ?? "").trim();
  if (!id) {
    return NextResponse.json({ error: "Thiếu lịch hẹn." }, { status: 400 });
  }
  return proxyJsonToBackend(
    "POST",
    `/api/v1/appointments/${encodeURIComponent(id)}/bao-xep-bac-si`,
    { ghi_chu: body.ghi_chu ?? null },
  );
}
