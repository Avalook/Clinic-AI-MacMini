// POST /api/doi-tac/lenh  { lenh, chi_dinh_id, ly_do?, xac_nhan? }
// Ba lệnh của luồng đối tác chung (Tuyền 16/10/2026): Trả kết quả, hoàn tác Trả
// kết quả, hoàn tác Nhận mẫu. Luật ở máy chủ — `DoiTacService`. Tầng này chỉ
// kiểm hình dạng mã + tên lệnh để chuỗi tự do không nối được vào URL backend.

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const LENH = new Set(["tra-ket-qua", "huy-tra-ket-qua", "huy-nhan-mau"]);

export async function POST(request: Request) {
  const than = (await request.json().catch(() => null)) as {
    lenh?: unknown;
    chi_dinh_id?: unknown;
    ly_do?: unknown;
    xac_nhan?: unknown;
  } | null;
  const lenh = typeof than?.lenh === "string" ? than.lenh : "";
  const id = typeof than?.chi_dinh_id === "string" ? than.chi_dinh_id : "";
  if (!LENH.has(lenh) || !UUID_RE.test(id)) {
    return NextResponse.json(
      { error: "BAD_REQUEST", message: "Lệnh hoặc mã việc không hợp lệ." },
      { status: 400 },
    );
  }
  return proxyJsonToBackend(
    "POST",
    `/api/v1/doi-tac/viec/${encodeURIComponent(id)}/${lenh}`,
    lenh === "tra-ket-qua"
      ? {}
      : {
          ly_do: typeof than?.ly_do === "string" ? than.ly_do : null,
          xac_nhan: than?.xac_nhan === true,
        },
  );
}
