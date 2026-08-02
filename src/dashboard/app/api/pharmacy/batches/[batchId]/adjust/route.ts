// POST /api/pharmacy/batches/[batchId]/adjust — điều chỉnh tồn sau kiểm kê.
// Âm = giảm, dương = tăng. Lý do bắt buộc; luật nằm ở FastAPI.

import {
  badRequest,
  forwardPharmacyWrite,
  isUuid,
  readJsonObject,
} from "../../../../../../lib/pharmacy-proxy";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ batchId: string }> },
) {
  const { batchId } = await params;
  if (!isUuid(batchId)) return badRequest("Mã lô không hợp lệ.");

  const raw = await readJsonObject(request);
  if (!raw) return badRequest("JSON không hợp lệ.");

  return forwardPharmacyWrite(
    request,
    `/api/v1/pharmacy/batches/${batchId}/adjust`,
    { quantity: raw.quantity, reason: raw.reason ?? "" },
  );
}
