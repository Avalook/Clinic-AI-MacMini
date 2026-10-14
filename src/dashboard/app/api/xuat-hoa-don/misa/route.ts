// "Đã xuất sang MISA" (G5c): danh sách các lần xuất + đánh dấu một khoảng ngày. Proxy
// mỏng — máy chủ tự dựng lại danh sách hoá đơn của khoảng, kiểm quyền kế toán và ngày.

import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

export async function GET() {
  return proxyJsonToBackend("GET", "/api/v1/hoa-don/misa-xuat", undefined);
}

export async function POST(request: Request) {
  const body = await request.json().catch(() => ({}));
  return proxyJsonToBackend("POST", "/api/v1/hoa-don/misa-xuat", body);
}
