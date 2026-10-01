// /api/payment — chốt / hoàn tác thu tiền 1 khâu của 1 lượt khám.
//   POST   { visitId, clinicPatientId?, kind, billRevision?, amount?, method? }
//          → một LẦN THU. method CASH (mặc định) → ĐÃ THU; TRANSFER/QR → CHỜ XÁC MINH.
//          Số tiền do máy chủ tính (contract tiền–thuốc C3); amount chỉ để đối chiếu.
//   POST   { action: "xac-minh", paymentCycleId, visitId, kind, reference }
//          → chuyển khoản/QR đã nhận. Mọi lệnh sau khi đã có lần thu nhắm ĐÚNG
//          paymentCycleId (review CP2 #1) — lệnh cũ đến muộn không trượt sang lần sau.
//   POST   { action: "huy-cho", paymentCycleId, visitId, kind, reason } → huỷ lần chờ.
//   POST   { action: "hoan-tien" | "hoan-tien-xac-nhan" | "hoan-tien-dong", … } → CP5.
//   POST   { action: "doi-hinh-thuc", paymentCycleId, hinhThuc?, hinhThucCu?, reference?, lyDo?,
//            tienMat?, chuyenKhoan? }
//          → đổi hình thức phiếu ĐÃ THU (V7; 01/10 thêm CHIA TM + CK) — sổ chỉ thêm.
//   POST   { action: "hoan-tac", paymentCycleId, lyDo? } → HOÀN TÁC lần thu (01/10/2026):
//          đã thu → huỷ phiếu; chuyển khoản chờ → huỷ lần chờ. Lý do tuỳ chọn.
//   POST   (thu) thêm `phan: [{hinh_thuc, so_tien, khach_dua?}]` — chia Tiền mặt +
//          Chuyển khoản (01/10/2026); QR cũ = Chuyển khoản.
//   DELETE { paymentCycleId, visitId, kind, reason }     → huỷ đúng phiếu, có lý do.
// kind = 'thuoc' | 'dich_vu'. `quay` (01/10/2026) = quầy màn đang đứng — thuốc và
// dịch vụ thu riêng hẳn; khác `kind` thì máy chủ trả 409 QUAY_KHAC_LOAI.
//
// Toàn bộ luật nằm ở FastAPI (ADR-0012): vai nào được thu khâu nào, chốt "chỉ
// thu khi bác sĩ đã khám xong" (visit.exam_completed_at), ghi sổ + audit
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
    paymentCycleId?: string;
    /** Quầy màn đang đứng — máy chủ gác thuốc / dịch vụ thu riêng (01/10/2026). */
    quay?: "dich_vu" | "thuoc";
    refundId?: string;
    trangThai?: string;
    hinhThuc?: string | null;
    hinhThucCu?: string | null;
    lyDo?: string | null;
    tienMat?: number | null;
    chuyenKhoan?: number | null;
    /** Chia lần thu theo hình thức (01/10/2026). */
    phan?: { hinh_thuc: string; so_tien: number; khach_dua?: number | null }[];
    dong?: { payment_bill_line_id: string; so_luong: number }[];
    /** Quầy một hoá đơn (27/09): lựa chọn dịch vụ khách đang nhìn lúc bấm Thu. */
    chon?: {
      order_ids_seen: string[];
      selected_order_ids: string[];
      expected_selection_revision: number;
    };
  };
  // CP5 — hoàn tiền (tạm thời chỉ Quản lý, máy chủ kiểm; số tiền máy chủ tính).
  if (p.action === "hoan-tien") {
    // Chống gửi trùng (review CP5 P1-A): cùng khoá → máy chủ trả lại kết quả
    // lần đầu, không tạo khoản hoàn thứ hai.
    return proxyJsonToBackend(
      "POST",
      "/api/v1/payments/hoan-tien",
      {
        payment_cycle_id: p.paymentCycleId,
        visit_id: p.visitId,
        kind: p.kind,
        method: p.method,
        reason: p.reason,
        dong: p.dong,
      },
      request.headers.get("Idempotency-Key") ?? undefined,
    );
  }
  if (p.action === "hoan-tien-xac-nhan") {
    return proxyJsonToBackend("POST", "/api/v1/payments/hoan-tien/xac-nhan", {
      refund_id: p.refundId,
      reference: p.reference,
    });
  }
  if (p.action === "hoan-tien-dong") {
    return proxyJsonToBackend("POST", "/api/v1/payments/hoan-tien/dong", {
      refund_id: p.refundId,
      trang_thai: p.trangThai,
      reason: p.reason,
    });
  }
  if (p.action === "doi-hinh-thuc") {
    return proxyJsonToBackend("POST", "/api/v1/payments/doi-hinh-thuc", {
      payment_cycle_id: p.paymentCycleId,
      hinh_thuc: p.hinhThuc,
      hinh_thuc_cu: p.hinhThucCu ?? null,
      reference: p.reference ?? null,
      ly_do: p.lyDo ?? null,
      tien_mat: p.tienMat ?? null,
      chuyen_khoan: p.chuyenKhoan ?? null,
    });
  }
  if (p.action === "hoan-tac") {
    return proxyJsonToBackend("POST", "/api/v1/payments/hoan-tac", {
      payment_cycle_id: p.paymentCycleId,
      ly_do: p.lyDo ?? null,
      quay: p.quay ?? null,
    });
  }
  if (p.action === "xac-minh") {
    return proxyJsonToBackend("POST", "/api/v1/payments/xac-minh", {
      payment_cycle_id: p.paymentCycleId,
      visit_id: p.visitId,
      kind: p.kind,
      reference: p.reference,
      quay: p.quay ?? null,
    });
  }
  if (p.action === "huy-cho") {
    return proxyJsonToBackend("POST", "/api/v1/payments/huy-cho", {
      payment_cycle_id: p.paymentCycleId,
      visit_id: p.visitId,
      kind: p.kind,
      reason: p.reason,
      quay: p.quay ?? null,
    });
  }
  // Tiền dịch vụ (Lifecycle v1 Slice 3): backend BẮT BUỘC khoá gửi lại và
  // giữ biên nhận trong cùng giao dịch — chuyển nguyên khoá của màn hình.
  return proxyJsonToBackend(
    "POST",
    "/api/v1/payments",
    {
      visit_id: p.visitId,
      clinic_patient_id: p.clinicPatientId || null,
      kind: p.kind,
      amount: p.amount,
      bill_revision: p.billRevision || null,
      method: p.method || "CASH",
      quay: p.quay ?? null,
      ...(p.chon ? { chon: p.chon } : {}),
      ...(p.phan ? { phan: p.phan } : {}),
    },
    request.headers.get("Idempotency-Key") ?? undefined,
  );
}

export async function DELETE(request: Request) {
  const raw = await body(request);
  if (raw === undefined) {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const p = (raw ?? {}) as {
    paymentCycleId?: string;
    visitId?: string;
    kind?: string;
    reason?: string;
  };
  return proxyJsonToBackend("DELETE", "/api/v1/payments", {
    payment_cycle_id: p.paymentCycleId,
    visit_id: p.visitId,
    kind: p.kind,
    reason: p.reason,
  });
}
