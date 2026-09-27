// POST /api/doi-tac/da-thu-tien  { chi_dinh_id, so_tien, hinh_thuc, ghi_chu? }
// Đối tác ghi nhận ĐÃ THU tiền khách (khách trả trực tiếp cho đối tác — Tuyền
// chốt 27/09/2026). Luật (việc nào ghi được, số tiền, hình thức) nằm ở máy chủ —
// `DoiTacService.ghi_nhan_da_thu`.

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function POST(request: Request) {
  const than = (await request.json().catch(() => null)) as {
    chi_dinh_id?: unknown;
    so_tien?: unknown;
    hinh_thuc?: unknown;
    ghi_chu?: unknown;
  } | null;
  const id = typeof than?.chi_dinh_id === "string" ? than.chi_dinh_id : "";
  if (!UUID_RE.test(id)) {
    return NextResponse.json(
      { error: "BAD_REQUEST", message: "Mã việc không hợp lệ." },
      { status: 400 },
    );
  }
  return proxyJsonToBackend(
    "POST",
    `/api/v1/doi-tac/viec/${encodeURIComponent(id)}/da-thu-tien`,
    {
      // Kiểu thô — máy chủ đọc ("900.000", 900000…) và trả câu lỗi.
      so_tien:
        typeof than?.so_tien === "string" || typeof than?.so_tien === "number"
          ? than.so_tien
          : null,
      hinh_thuc: typeof than?.hinh_thuc === "string" ? than.hinh_thuc : null,
      ghi_chu:
        typeof than?.ghi_chu === "string" && than.ghi_chu.trim()
          ? than.ghi_chu.trim()
          : null,
    },
  );
}
