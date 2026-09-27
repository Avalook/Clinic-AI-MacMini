// Ghi kết quả một cuộc gọi nhắc tái khám.
//
// Đường ghi duy nhất cho hàng đợi `nhac_tai_kham`. Kết quả BẮT BUỘC và được
// backend canh bằng CHECK — không có nhánh nào ghi "đã gọi" mà bỏ trống kết
// quả, vì đó chính là lỗi mà màn CSKH cũ mắc phải: ba nút kết quả gửi lên một
// trường không ai nhận, nên cả ba ghi ra một dòng giống hệt nhau.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../../../lib/supabase-server";
import { proxyJsonToBackend } from "../../../../../lib/backend-proxy";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  // Cửa quyền là việc của BACKEND (crm.manage — lego Chăm sóc khách hàng) — proxy chỉ kiểm đã đăng nhập
  // (kiểm toán 27/09/2026: cửa vai ở đây chặn người đã được cấp lego).

  const { id } = await params;
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  return proxyJsonToBackend(
    "POST",
    `/api/v1/cskh/recall-jobs/${encodeURIComponent(id)}/ket-qua`,
    body,
  );
}
