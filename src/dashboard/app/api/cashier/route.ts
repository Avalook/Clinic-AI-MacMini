// /api/cashier — người đang chờ thu tiền hôm nay.
//
// Chuyển tiếp thẳng `/api/v1/cashier/board`. Ô nào hiện (thuốc / dịch vụ) do
// `modes` quyết định, còn VAI NÀO ĐƯỢC XEM thì FastAPI gác — lớp này không tự
// suy ra quyền từ vai, vì thế là viết luật lần thứ hai bằng ngôn ngữ khác.

import { NextResponse } from "next/server";
import { fetchFromBackend } from "../../../lib/backend-proxy";

export async function GET(request: Request) {
  const modes = new URL(request.url).searchParams.get("modes") ?? "dich_vu,thuoc";
  const d = await fetchFromBackend<{ items: unknown[]; paid: unknown[] }>(
    `/api/v1/cashier/board?modes=${encodeURIComponent(modes)}`,
  );
  if (d === null) {
    // null = không với tới backend. Trả danh sách rỗng ở đây thì quầy nói dối
    // "hôm nay không ai chờ thu", và thu ngân đóng máy đi về.
    return NextResponse.json(
      { error: "Không đọc được danh sách chờ thu" },
      { status: 502 },
    );
  }
  return NextResponse.json(d, {
    headers: { "Cache-Control": "private, no-store" },
  });
}
