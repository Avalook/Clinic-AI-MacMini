// Thuế suất GTGT cho kế toán (G5b/C2): xem thuế theo nhóm + tìm mặt hàng. Proxy mỏng —
// quyền (`accounting.finance.full` hoặc `accounting.tax.manage`) và chuẩn hoá do máy chủ quyết.

import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

export async function GET(request: Request) {
  const tim = new URL(request.url).searchParams.get("tim") ?? "";
  const q = new URLSearchParams();
  if (tim.trim()) q.set("tim", tim.slice(0, 80));
  return proxyJsonToBackend("GET", `/api/v1/ke-toan/thue-suat?${q}`, undefined);
}
