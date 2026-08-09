// CSKH gõ tay ngày tái khám cho một khách.
//
//   POST { clinic_patient_id, ngay_tai_kham, ly_do? }
//     → sinh HAI mốc gọi: trước 7 ngày (mời đặt lịch) và trước 1 ngày (nhắc đi
//       khám). Cả hai vào bảng `nhac_tai_kham`, nên chúng hiện lên ở cột
//       "Bước tiếp theo" của Quản lý khách hàng qua view v_trang_thai_cskh.
//
// VÌ SAO CẦN ĐƯỜNG NÀY. Việc nhắc tái khám tự sinh chỉ đọc được lời dặn nằm
// trong `soap_plan.tai_kham.ngay` của một phiếu khám ĐÃ CHỐT. Khách nói qua
// điện thoại "tháng sau em quay lại" thì không có phiếu nào để đọc — câu ấy
// trước đây không có chỗ nào ghi xuống, nên nó nằm trong đầu người trực và mất
// khi đổi ca.

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  return proxyJsonToBackend("POST", "/api/v1/cskh/nhac-tai-kham", body);
}
