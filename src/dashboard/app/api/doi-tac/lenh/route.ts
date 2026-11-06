// POST /api/doi-tac/lenh  { lenh, chi_dinh_id, ly_do?, xac_nhan?, mo_lai_phong? }
// Ba lệnh của luồng đối tác chung (Tuyền 16/10/2026): Trả kết quả, hoàn tác Trả
// kết quả, hoàn tác Nhận mẫu. Luật ở máy chủ — `DoiTacService`. Tầng này chỉ
// kiểm hình dạng mã + tên lệnh để chuỗi tự do không nối được vào URL backend
// (`lib/lenh-doi-tac.ts`).

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../../lib/backend-proxy";
import { docLenhDoiTac } from "../../../../lib/lenh-doi-tac";

export async function POST(request: Request) {
  const lenh = docLenhDoiTac(await request.json().catch(() => null));
  if (lenh === null) {
    return NextResponse.json(
      { error: "BAD_REQUEST", message: "Lệnh hoặc mã việc không hợp lệ." },
      { status: 400 },
    );
  }
  return proxyJsonToBackend(
    "POST",
    `/api/v1/doi-tac/viec/${encodeURIComponent(lenh.chi_dinh_id)}/${lenh.lenh}`,
    lenh.du_lieu,
  );
}
