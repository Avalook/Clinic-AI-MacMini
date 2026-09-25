// Proxy các thao tác nhà thuốc xuống FastAPI.
//
// Trước đây bốn màn /pharmacy đọc thẳng Supabase và KHÔNG có đường ghi nào —
// RLS chỉ cấp SELECT, nên kể cả gắn nút thì trình duyệt cũng không ghi được.
// Mọi thao tác kho đi qua đây.
//
// Danh sách trắng ở dưới quyết định đường nào hợp lệ. Một `[action]` trần sẽ
// mở luôn cả những đường thêm sau này mà chưa ai cân nhắc có nên cho trình
// duyệt gọi không.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../../lib/supabase-server";
import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

/** Thao tác cho phép → đường backend. */
const ACTIONS: Record<string, string> = {
  receive: "/api/v1/pharmacy/receive",
  dispense: "/api/v1/pharmacy/dispense",
  refuse: "/api/v1/pharmacy/refuse",
  "close-line": "/api/v1/pharmacy/close-line",
  adjust: "/api/v1/pharmacy/adjust",
  discard: "/api/v1/pharmacy/discard",
  // Contract tiền–thuốc CP4: xác định thuốc kho, số mua, chọn / bỏ / đổi lô.
  "xac-dinh-thuoc": "/api/v1/pharmacy/xac-dinh-thuoc",
  "so-luong-mua": "/api/v1/pharmacy/so-luong-mua",
  "phan-lo": "/api/v1/pharmacy/phan-lo",
  "bo-phan-lo": "/api/v1/pharmacy/bo-phan-lo",
  "doi-lo": "/api/v1/pharmacy/doi-lo",
  // CP5: huỷ phần đã bán chưa giao (cần căn cứ), khách trả thuốc (chưa xử lý).
  "huy-phan-chua-giao": "/api/v1/pharmacy/huy-phan-chua-giao",
  "khach-tra": "/api/v1/pharmacy/khach-tra",
  // 25/09: Kho thuốc — thêm / sửa thuốc trong danh mục (tên, giá, hướng dẫn).
  "luu-thuoc": "/api/v1/pharmacy/danh-muc",
};

export async function POST(
  request: Request,
  { params }: { params: Promise<{ action: string }> },
) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  // Không gác vai ở proxy (24/09/2026): backend hỏi QUYỀN "Nhà thuốc"
  // (`pharmacy.dispense`) — người được cấp khối trên màn Phân quyền làm được
  // ngay, không ăn 403 ở cửa ngoài.

  const { action } = await params;
  const path = ACTIONS[action];
  if (!path) {
    return NextResponse.json(
      { error: `Thao tác không hợp lệ: ${action}` },
      { status: 400 },
    );
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  // Chuyển tiếp khoá chống-gửi-trùng (review CP5 P1-A). Trước bản này proxy
  // KHÔNG chuyển header, nên chốt chống trùng của /pharmacy/dispense (16/09)
  // chưa từng chạy khi bấm từ giao diện.
  const khoa = request.headers.get("Idempotency-Key") ?? undefined;
  return proxyJsonToBackend("POST", path, body, khoa);
}
