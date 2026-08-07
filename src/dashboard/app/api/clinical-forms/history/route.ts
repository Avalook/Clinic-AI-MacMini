// Lượt khám trước của một bệnh nhân.
//
// Backend lọc theo phòng khám của người gọi và gác vai lâm sàng, nên không có
// đường nào để một vai không khám đọc bệnh án cũ qua đây.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../../lib/supabase-server";
import { fetchFromBackend } from "../../../../lib/backend-proxy";

export async function GET(request: Request) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  const id = new URL(request.url).searchParams.get("clinic_patient_id");
  if (!id) {
    return NextResponse.json({ error: "Thiếu clinic_patient_id" }, { status: 400 });
  }

  const d = await fetchFromBackend<{ items: unknown[] }>(
    `/api/v1/clinical-forms/history?clinic_patient_id=${encodeURIComponent(id)}`,
  );
  // null = backend không với tới. Trả danh sách rỗng thì màn hình nói dối
  // "bệnh nhân chưa khám lần nào" — đúng loại im lặng nguy hiểm nhất ở đây.
  if (d === null) {
    return NextResponse.json({ error: "Không đọc được lượt khám trước" }, { status: 502 });
  }
  return NextResponse.json(d);
}
