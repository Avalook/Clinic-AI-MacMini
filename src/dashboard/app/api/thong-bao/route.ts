// Thông báo chưa xử lý dành cho vai của tôi.
//
// MỌI vai đọc được của mình — chuông ở thanh trên cùng gọi đường này mỗi 20
// giây, trên mọi trang. Backend lọc theo `identity.role`, nên không có tham số
// nào để một người hỏi thông báo của người khác.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../lib/supabase-server";
import {
  fetchFromBackend,
  proxyJsonToBackend,
} from "../../../lib/backend-proxy";

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

/** Tắt chấm đỏ — đóng dấu ĐÃ ĐỌC, KHÔNG đóng việc.
 *
 *  Nút "Đánh dấu đã đọc" trước đây chỉ gọi `setUnread(0)` trong trình duyệt,
 *  mà con số trên chuông là `unread + thongBao.length`: phần đến từ máy chủ
 *  không có đường nào tắt. Tải lại trang là đỏ y như cũ. */
export async function POST() {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  return proxyJsonToBackend("POST", "/api/v1/thong-bao/da-doc", {});
}
