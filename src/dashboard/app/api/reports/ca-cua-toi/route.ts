import { proxyJsonToBackend } from "@/lib/backend-proxy";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const q = new URLSearchParams();
  // Chuyển nguyên ca/cơ sở: máy chủ từ chối mã rác hoặc ngoài lịch trực.
  // Không nhận ngày, không có đường xuất báo cáo tổng hợp bằng report.view.
  for (const key of ["ca", "co_so", "loai"]) {
    const value = url.searchParams.get(key);
    if (value !== null) q.set(key, value);
  }
  return proxyJsonToBackend("GET", `/api/v1/reports/ca-cua-toi?${q}`, undefined);
}
