// Giờ ba ca làm việc — quản lý tự sửa, không phải gọi người viết code.
//
//   GET   → giờ từng ca + giờ mở cửa từng thứ (để màn hình cảnh báo tại chỗ)
//   PATCH { ca_lam_viec: { SANG: {bat_dau, ket_thuc}, … } }
//
// Đi qua FastAPI. `clinic.settings` KHÔNG mở đường ghi cho client — cột ấy đã
// bị gỡ khỏi GRANT của `authenticated` (A.5) vì từng chứa credential POS.
//
// DÙNG `proxyJsonToBackend` CHO PATCH, không dùng `fetchFromBackend`: backend
// trả 422 kèm DANH SÁCH lỗi cấu hình ("ca Tối tràn ngoài giờ đóng cửa thứ
// Bảy"), và `fetchFromBackend` trả `null` cho mọi lỗi nên câu ấy sẽ biến mất,
// người dùng chỉ còn thấy "không lưu được".

import { NextResponse } from "next/server";

import {
  fetchFromBackend,
  proxyJsonToBackend,
} from "../../../lib/backend-proxy";

export interface CaLamViecResponse {
  ca_lam_viec: Record<
    string,
    { bat_dau: string; ket_thuc: string; nhan: string }
  >;
  gio_mo_cua: Record<string, { mo: string; dong: string }>;
}

export async function GET() {
  const data = await fetchFromBackend<CaLamViecResponse>(
    "/api/v1/ca-lam-viec",
  );
  // null = không gọi được backend. Trả 503 chứ đừng trả cấu hình rỗng: màn hình
  // hiện ba ô giờ trống trông y hệt "phòng khám chưa khai ca", và quản lý sẽ gõ
  // lại từ đầu rồi ghi đè lên cấu hình đang chạy tốt.
  if (data === null) {
    return NextResponse.json(
      { error: "Không đọc được giờ ca làm việc." },
      { status: 503 },
    );
  }
  return NextResponse.json(data);
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
