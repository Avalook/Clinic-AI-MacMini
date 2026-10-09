// /api/reports/ca-cua-toi — Báo cáo CA CỦA TÔI (09/10/2026), chỉ đọc.
//
// Chuyển tiếp thẳng `/api/v1/reports/ca-cua-toi`. Lớp này chỉ kiểm đăng nhập;
// máy chủ soát lịch trực (ca nào, cơ sở nào được xem) và cắt khối bị ẩn. KHÔNG
// nhận ngày — máy chủ luôn lấy hôm nay. `ca` / `co_so` chuyển nguyên (cắt độ
// dài) để máy chủ trả 403 cho giá trị rác, không để lớp này đổi sang ca khác.

import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const q = new URLSearchParams();
  const ca = url.searchParams.get("ca") ?? "";
  if (ca) q.set("ca", ca.slice(0, 10));
  const coSo = url.searchParams.get("co_so") ?? "";
  if (coSo) q.set("co_so", coSo.slice(0, 64));
  const loai = url.searchParams.get("loai");
  if (loai === "dich_vu" || loai === "thuoc") q.set("loai", loai);
  return proxyJsonToBackend("GET", `/api/v1/reports/ca-cua-toi?${q.toString()}`, undefined);
}
