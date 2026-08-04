// Cờ dưới ngưỡng WHO + gợi ý xét nghiệm di truyền cho phiếu Nam khoa.
//
// CHUYỂN TIẾP THUẦN. Không ngưỡng nào, không luật nào ở đây — đó là cả lý do
// tồn tại của đường này: WHO đã đổi ngưỡng qua ba ấn bản, và chúng phải sống ở
// bảng `semen_reference_range` chứ không ở trình duyệt.
//
// POST chứ không GET vì nó nhận form đang gõ dở: bác sĩ cần thấy cờ ngay khi
// nhập tinh dịch đồ, không phải sau khi bấm lưu. Và nội dung lâm sàng không nên
// nằm trong query string, nơi nó đi thẳng vào log máy chủ.
import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../../lib/supabase-server";
import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

export async function POST(request: Request) {
  const supabase = await getSupabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user)
    return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  const body = await request.json().catch(() => ({}));
  return proxyJsonToBackend(
    "POST",
    "/api/v1/clinical-forms/andrology-review",
    body,
  );
}
