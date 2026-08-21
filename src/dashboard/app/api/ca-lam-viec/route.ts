// Giờ ba ca làm việc — quản lý tự sửa, không phải gọi người viết code.
//
//   GET   → giờ từng ca + giờ mở cửa từng thứ (để màn hình cảnh báo tại chỗ)
//   PATCH { ca_lam_viec: { SANG: {bat_dau, ket_thuc}, … } }
//
// Đi qua FastAPI. `clinic.settings` KHÔNG mở đường ghi cho client — cột ấy đã
// bị gỡ khỏi GRANT của `authenticated` (A.5) vì từng chứa credential POS.
//
// CẢ HAI ĐƯỜNG đều đi qua `proxyJsonToBackend` — nó chuyển tiếp NGUYÊN mã
// trạng thái và câu lỗi của FastAPI. Đường đọc cần thế vì backend trả 403 cho
// người không đủ quyền (chỉ Trưởng ca + Quản lý); đường ghi cần thế vì backend
// trả 422 kèm DANH SÁCH lỗi cấu hình ("ca Tối tràn ngoài giờ đóng cửa thứ
// Bảy"). Lối tắt `fetchFromBackend` trả `null` cho MỌI lỗi nên nó xoá sạch
// khác biệt ấy — xem thêm chú thích trong chính hàm GET bên dưới.

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "../../../lib/backend-proxy";

export interface CaLamViecResponse {
  ca_lam_viec: Record<
    string,
    { bat_dau: string; ket_thuc: string; nhan: string }
  >;
  gio_mo_cua: Record<string, { mo: string; dong: string }>;
}

export async function GET() {
  // DÙNG proxyJsonToBackend, KHÔNG dùng fetchFromBackend.
  //
  // `fetchFromBackend` trả `null` cho MỌI lỗi, nên route này từng biến 403
  // "không đủ quyền" thành 503 "máy chủ hỏng". Đo tải 100 người dùng ảo ngày
  // 22/08/2026 phát hiện: Lễ tân và CSKH mở trang nào chạm đường này cũng nhận
  // 503 — 240/240 lượt. Endpoint chỉ mở cho Trưởng ca + Quản lý (đúng), nhưng
  // câu trả lời nói sai bản chất, và 503 trong log lúc có sự cố thật là một
  // dấu vết dẫn sai. Đây đúng cái bẫy đã ghi ngay trong `backend-proxy.ts`.
  //
  // `proxyJsonToBackend` giữ nguyên mã trạng thái và câu lỗi của FastAPI, nên
  // 403 vẫn là 403 và 503 chỉ còn nghĩa "backend thật sự không gọi được" —
  // lúc đó màn hình mới hiện cảnh báo "đừng nhập mới kẻo ghi đè".
  return proxyJsonToBackend("GET", "/api/v1/ca-lam-viec", undefined);
}

export async function PATCH(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  return proxyJsonToBackend("PATCH", "/api/v1/ca-lam-viec", body);
}
