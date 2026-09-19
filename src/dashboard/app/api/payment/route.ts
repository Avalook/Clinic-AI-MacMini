// /api/payment — chốt / hoàn tác thu tiền 1 khâu của 1 lượt khám.
//   POST   { visitId, clinicPatientId?, kind, billRevision?, amount?, method? }
//          → một LẦN THU. method CASH (mặc định) → ĐÃ THU; TRANSFER/QR → CHỜ XÁC MINH.
//          Số tiền do máy chủ tính (contract tiền–thuốc C3); amount chỉ để đối chiếu.
//   POST   { action: "xac-minh", visitId, kind, reference } → chuyển khoản/QR đã nhận.
//   POST   { action: "huy-cho", visitId, kind, reason }     → huỷ lần chờ xác minh.
//   DELETE { visitId, kind, reason }                     → hoàn tác có lý do.
// kind = 'thuoc' | 'dich_vu'.
//
// Toàn bộ luật nằm ở FastAPI (ADR-0012): vai nào được thu khâu nào, chốt "chỉ
// thu khi bác sĩ đã khám xong" (appointment.status = COMPLETED), ghi sổ + audit
// trong cùng một transaction. Route này chỉ chuyển tiếp kèm token người gọi —
// không còn service-role, nên nó không thể đọc/ghi ngoài phòng khám của họ.

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../lib/backend-proxy";

async function body(request: Request): Promise<unknown | undefined> {
  try {
    return await request.json();
  } catch {
    return undefined;
  }
}

export async function POST(request: Request) {
  const raw = await body(request);
  if (raw === undefined) {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const p = (raw ?? {}) as {
    action?: string;
    visitId?: string;
    clinicPatientId?: string;
    kind?: string;
    amount?: number;
    billRevision?: string;
    method?: string;
    reference?: string;
    reason?: string;
  };
  if (p.action === "xac-minh") {
    return proxyJsonToBackend("POST", "/api/v1/payments/xac-minh", {
      visit_id: p.visitId,
      kind: p.kind,
      reference: p.reference,
    });
  }
  if (p.action === "huy-cho") {
    return proxyJsonToBackend("POST", "/api/v1/payments/huy-cho", {
      visit_id: p.visitId,
      kind: p.kind,
      reason: p.reason,
    });
  }
  return proxyJsonToBackend("POST", "/api/v1/payments", {
    visit_id: p.visitId,
    clinic_patient_id: p.clinicPatientId || null,
    kind: p.kind,
    amount: p.amount,
    bill_revision: p.billRevision || null,
    method: p.method || "CASH",
  });
}

export async function DELETE(request: Request) {
  const raw = await body(request);
  if (raw === undefined) {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const p = (raw ?? {}) as { visitId?: string; kind?: string; reason?: string };
  return proxyJsonToBackend("DELETE", "/api/v1/payments", {
    visit_id: p.visitId,
    kind: p.kind,
    reason: p.reason,
  });
}
