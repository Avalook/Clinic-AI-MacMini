// GET /api/appointments/tim-khach?q=
// Ô "Tìm kiếm khách hàng có sẵn" của màn Đặt lịch — tìm trên TOÀN BỘ hồ sơ
// (06/10/2026, sau khi nạp ~8.600 khách cũ từ Notion). Proxy mỏng; cách tìm,
// thứ tự và trần 20 kết quả ở `man_dat_lich_doc.tim_khach`. `q` rác → máy chủ
// trả danh sách rỗng, nên ở đây không tự kiểm gì thêm.

import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

export async function GET(request: Request) {
  const q = new URL(request.url).searchParams.get("q") ?? "";
  return proxyJsonToBackend(
    "GET",
    `/api/v1/appointments/tim-khach?${new URLSearchParams({ q }).toString()}`,
    null,
  );
}
