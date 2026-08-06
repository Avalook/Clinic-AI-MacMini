// Thông báo chưa xử lý dành cho vai của tôi.
//
// MỌI vai đọc được của mình — chuông ở thanh trên cùng gọi đường này mỗi 20
// giây, trên mọi trang. Backend lọc theo `identity.role`, nên không có tham số
// nào để một người hỏi thông báo của người khác.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { fetchFromBackend } from "../../../lib/backend-proxy";

export async function GET() {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  // null = backend không với tới. Trả danh sách rỗng thì chuông im lặng nói
  // dối "không có gì" — nên nói ra bằng mã trạng thái.
  const d = await fetchFromBackend<{ items: unknown[] }>("/api/v1/thong-bao");
  if (d === null) {
    return NextResponse.json(
      { error: "Không đọc được thông báo" },
      { status: 502 },
    );
  }
  return NextResponse.json(d);
}
