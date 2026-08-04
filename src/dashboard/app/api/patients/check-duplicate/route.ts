// /api/patients/check-duplicate?phone=&full_name=&birth_year=
//
// Cảnh báo SỚM hồ sơ có thể trùng, dùng CHUNG một luật với lúc lưu.
//
// Đường cũ (/api/patients/check-phone) tự viết truy vấn Supabase riêng và chỉ
// so số điện thoại. Luật lúc LƯU thì so cả CCCD và — từ nay — họ tên + năm
// sinh. Hai luật khác nhau cho cùng một câu hỏi nghĩa là Lễ tân được báo "không
// trùng", bấm lưu, rồi hồ sơ rơi vào hàng chờ gộp mà không ai hiểu vì sao.
//
// Route này chuyển tiếp xuống FastAPI, nơi gọi đúng hàm mà đường lưu gọi.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../../lib/supabase-server";
import { getClinicRole } from "../../../../lib/clinic-session";
import { canWriteIntake } from "../../../../lib/roles";
import { fetchFromBackend } from "../../../../lib/backend-proxy";

const EMPTY = { exists: false, matches: [] as unknown[] };

export async function GET(request: Request) {
  const supabase = await getSupabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json(EMPTY, { status: 401 });

  // Chỉ vai được tạo hồ sơ mới thấy danh sách này — nó là dữ liệu bệnh nhân.
  const role = await getClinicRole();
  if (!canWriteIntake(role)) return NextResponse.json(EMPTY, { status: 403 });

  const sp = new URL(request.url).searchParams;
  const qs = new URLSearchParams();
  for (const k of ["phone", "full_name", "birth_year"]) {
    const v = sp.get(k)?.trim();
    if (v) qs.set(k, v);
  }
  if ([...qs.keys()].length === 0) return NextResponse.json(EMPTY);

  // Backend im lặng thì KHÔNG nói "không trùng" — trả rỗng nhưng đó là "chưa
  // kiểm được", và guard lúc LƯU vẫn chạy độc lập nên không ai lọt.
  const data = await fetchFromBackend<typeof EMPTY>(
    `/api/v1/patients/check-duplicate?${qs}`,
  );
  return NextResponse.json(data ?? EMPTY);
}
