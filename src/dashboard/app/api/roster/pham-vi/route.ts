// Ma trận "chức danh nào được xếp vào vị trí nào" — màn cấu hình của quản lý.
//
//   GET                                  → cả ma trận
//   PUT  { tram_ma, vai, cho_phep }      → bật/tắt một ô
//
// Đi qua FastAPI. Bảng không mở đường ghi cho client: sửa được ma trận là sửa
// được ai đứng ở bàn khám (ADR-0012).

import { NextResponse } from "next/server";
import {
  fetchFromBackend,
  proxyJsonToBackend,
} from "../../../../lib/backend-proxy";

export async function GET() {
  const data = await fetchFromBackend<{ items: unknown[] }>(
    "/api/v1/roster/station-scope",
  );
  // null = không gọi được backend. Trả 503 chứ đừng trả danh sách rỗng: màn
  // hình sẽ vẽ một ma trận trắng trơn và quản lý tưởng phòng khám chưa khai gì.
  if (data === null) {
    return NextResponse.json(
      { error: "Không đọc được phạm vi vị trí." },
      { status: 503 },
    );
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
  return proxyJsonToBackend("PUT", "/api/v1/roster/station-scope", body);
}
