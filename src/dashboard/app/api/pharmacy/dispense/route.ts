// POST /api/pharmacy/dispense — cấp thuốc, trừ kho theo FEFO.
//
// Số lượng do dược sĩ nhập chứ không suy từ đơn: `prescription.quantity` là text
// tự do ("30 viên", "1 hộp"). Đơn thuốc chỉ là tham chiếu trong sổ kho.

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
  const prescriptionId = raw.prescriptionId ?? null;
  if (prescriptionId !== null && !isUuid(prescriptionId)) {
    return badRequest("Mã đơn thuốc không hợp lệ.");
  }

  return forwardPharmacyWrite(request, "/api/v1/pharmacy/dispense", {
    drug_catalog_id: raw.drugCatalogId,
    quantity: raw.quantity,
    prescription_id: prescriptionId,
    reason: raw.reason ?? null,
  });
}
