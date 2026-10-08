// Chip liệu trình cho một LÔ lượt đang hiện (08/10/2026) — phòng dịch vụ, tiếp
// đón, hàng chờ bàn khám gọi MỘT lần cho cả danh sách, không gọi từng dòng.
//
//   GET ?luot=<visit_id>,<visit_id>,…
//     → { chi_dinh: {order_id: {visit_id, buoi_so, so_buoi, tra_truoc, …}},
//         khach: {visit_id: [{service_name, con_tra_truoc, …}]} }
//
// Chỉ là ống dẫn — mã rác máy chủ tự bỏ, trần 300 lượt.

import { proxyJsonToBackend } from "@/lib/backend-proxy";

export async function GET(request: Request) {
  const luot = (new URL(request.url).searchParams.get("luot") ?? "").slice(0, 12000);
  return proxyJsonToBackend(
    "GET",
    `/api/v1/lieu-trinh/chip?luot=${encodeURIComponent(luot)}`,
    undefined,
  );
}
