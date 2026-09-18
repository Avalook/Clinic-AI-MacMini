// Hồ sơ một lần khám (bản đọc gộp) — CSKH xem trước và tải PDF.
// Chỉ là ống dẫn: ai được xem, đọc gì, trạng thái duyệt… do FastAPI quyết.

import { proxyJsonToBackend } from "@/lib/backend-proxy";

export async function GET(
  _request: Request,
  ctx: { params: Promise<{ appointmentId: string }> },
) {
  const { appointmentId } = await ctx.params;
  return proxyJsonToBackend(
    "GET",
    `/api/v1/cskh/ho-so-kham/${encodeURIComponent(appointmentId)}`,
    undefined,
  );
}
