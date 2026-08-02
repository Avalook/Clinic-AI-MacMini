// POST /api/pharmacy/batches/[batchId]/discard — huỷ hàng (hết hạn, vỡ, hỏng).
// Bỏ trống quantity = huỷ toàn bộ phần còn lại của lô. Lý do bắt buộc.

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
    `/api/v1/pharmacy/batches/${batchId}/discard`,
    { quantity: raw.quantity ?? null, reason: raw.reason ?? "" },
  );
}
