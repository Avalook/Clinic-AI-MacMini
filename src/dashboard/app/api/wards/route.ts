// /api/wards?province=<code> → danh sách phường/xã của 1 tỉnh (sau sáp nhập, bỏ
// cấp huyện). Chỉ đọc danh mục hành chính dùng chung.
//
// 24/09/2026: đi qua backend `GET /api/v1/catalog/wards?province=` thay vì đọc
// thẳng bảng `ward` bằng Supabase — frontend chỉ là giao diện (SO-LUAT Phần 3).

import { NextResponse } from "next/server";
import { fetchFromBackend } from "../../../lib/backend-proxy";

export const dynamic = "force-dynamic";

interface Ward {
  code: string;
  name: string;
  full_name: string;
}

export async function GET(request: Request) {
  const province = new URL(request.url).searchParams.get("province")?.trim();
  if (!province) {
    return NextResponse.json({ wards: [] });
  }
  const data = await fetchFromBackend<Ward[]>(
    `/api/v1/catalog/wards?province=${encodeURIComponent(province)}`,
  );
  if (data === null) {
    return NextResponse.json(
      { error: "Không đọc được danh mục phường/xã." },
      { status: 502 },
    );
  }
  return NextResponse.json({
    wards: data.map(({ code, name, full_name }) => ({ code, name, full_name })),
  });
}
