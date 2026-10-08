// Liệu trình — danh sách cho CSKH và khung khách (08/10/2026).
//
//   GET ?loai=de_xuat                 → đề xuất chưa đăng ký
//   GET ?loai=dang_do&qua_ngay=14     → đang dở, quá X ngày chưa quay lại
//   GET ?loai=sap_het                 → sắp hết lộ trình (có lý do)
//   GET ?khach=<clinic_patient_id>    → mọi liệu trình của một khách
//
// Chỉ là ống dẫn: ai được xem, đếm buổi, trạng thái — FastAPI
// (`lieu_trinh_service.py`). Rác ở `qua_ngay` máy chủ tự về mặc định.

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "@/lib/backend-proxy";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function sai(message: string) {
  return NextResponse.json({ error: "BAD_REQUEST", message }, { status: 400 });
}

export async function GET(request: Request) {
  const q = new URL(request.url).searchParams;
  const khach = q.get("khach");
  if (khach !== null) {
    if (!UUID_RE.test(khach)) return sai("Mã khách không hợp lệ.");
    return proxyJsonToBackend("GET", `/api/v1/lieu-trinh/theo-khach/${khach}`, undefined);
  }
  const loai = q.get("loai");
  if (loai !== "de_xuat" && loai !== "dang_do" && loai !== "sap_het") {
    return sai("Thiếu ?loai=de_xuat|dang_do|sap_het hoặc ?khach=.");
  }
  const thamSo = new URLSearchParams({ loai });
  const quaNgay = q.get("qua_ngay");
  if (quaNgay) thamSo.set("qua_ngay", quaNgay.slice(0, 10));
  return proxyJsonToBackend("GET", `/api/v1/lieu-trinh/cskh?${thamSo.toString()}`, undefined);
}
