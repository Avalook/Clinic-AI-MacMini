// /api/payment — chốt / hoàn tác thu tiền 1 khâu của 1 lượt khám.
//   POST   { visitId, clinicPatientId?, kind, amount? }  → đánh dấu ĐÃ THU.
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
    visitId?: string;
    clinicPatientId?: string;
    kind?: string;
    amount?: number;
  };
  return proxyJsonToBackend("POST", "/api/v1/payments", {
    visit_id: p.visitId,
    clinic_patient_id: p.clinicPatientId || null,
    kind: p.kind,
    amount: p.amount,
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
