// Ghi kết quả một cuộc gọi nhắc tái khám.
//
// Đường ghi duy nhất cho hàng đợi `nhac_tai_kham`. Kết quả BẮT BUỘC và được
// backend canh bằng CHECK — không có nhánh nào ghi "đã gọi" mà bỏ trống kết
// quả, vì đó chính là lỗi mà màn CSKH cũ mắc phải: ba nút kết quả gửi lên một
// trường không ai nhận, nên cả ba ghi ra một dòng giống hệt nhau.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../../../lib/supabase-server";
import { getClinicRole } from "../../../../../lib/clinic-session";
import { proxyJsonToBackend } from "../../../../../lib/backend-proxy";

const VAI_DUOC_GHI = new Set(["CSKH", "MANAGEMENT", "TRUONG_CA"]);

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  const role = await getClinicRole();
  if (!role || !VAI_DUOC_GHI.has(role)) {
    return NextResponse.json(
      { error: "Chỉ CSKH / Trưởng ca / Quản lý mới ghi được kết quả cuộc gọi." },
      { status: 403 },
    );
  }

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
