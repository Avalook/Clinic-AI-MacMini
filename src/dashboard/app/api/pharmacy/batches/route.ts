// POST /api/pharmacy/batches — nhập hàng vào một lô (tạo lô nếu chưa có).
//
// Route mỏng: mọi luật (lô trùng mã khác hạn, số lượng hợp lệ, tồn không âm)
// nằm ở FastAPI + database. Ở đây chỉ chặn những thứ đủ để không gửi rác đi xa.

import {
  badRequest,
  forwardPharmacyWrite,
  isUuid,
  readJsonObject,
} from "../../../../lib/pharmacy-proxy";

export async function POST(request: Request) {
  const raw = await readJsonObject(request);
  if (!raw) return badRequest("JSON không hợp lệ.");

  if (!isUuid(raw.drugCatalogId)) return badRequest("Chưa chọn thuốc.");
  const batchCode = String(raw.batchCode ?? "").trim();
  if (!batchCode) return badRequest("Chưa nhập mã lô.");
  const expiryDate = String(raw.expiryDate ?? "").trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(expiryDate)) {
    return badRequest("Hạn dùng không hợp lệ.");
  }

  return forwardPharmacyWrite(request, "/api/v1/pharmacy/batches", {
    drug_catalog_id: raw.drugCatalogId,
    batch_code: batchCode,
    expiry_date: expiryDate,
    quantity: raw.quantity,
    unit: String(raw.unit ?? "viên").trim() || "viên",
    cost_price: raw.costPrice ?? null,
    reason: raw.reason ?? null,
  });
}
