// /api/cashier — người đang chờ thu tiền hôm nay.
//
// Chuyển tiếp thẳng `/api/v1/cashier/board`. Ô nào hiện (thuốc / dịch vụ) do
// `modes` quyết định, còn VAI NÀO ĐƯỢC XEM thì FastAPI gác — lớp này không tự
// suy ra quyền từ vai, vì thế là viết luật lần thứ hai bằng ngôn ngữ khác.

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../lib/backend-proxy";

const NGAY_RE = /^\d{4}-\d{2}-\d{2}$/;

export async function GET(request: Request) {
  const url = new URL(request.url);
  // Giao dịch đã ghi (xem lại, kể cả dòng đã huỷ) — batch pilot 18/09.
  if (url.searchParams.get("xem") === "giao-dich") {
    const q = new URLSearchParams();
    for (const k of ["tu", "den"]) {
      const v = url.searchParams.get(k) ?? "";
      if (NGAY_RE.test(v)) q.set(k, v);
    }
    return proxyJsonToBackend("GET", `/api/v1/cashier/giao-dich?${q.toString()}`, undefined);
  }
  const modes = url.searchParams.get("modes") ?? "dich_vu,thuoc";
  // Giữ NGUYÊN mã và câu của máy chủ: bị chặn quyền (403) phải nói là bị chặn,
  // không được thành "Không đọc được danh sách" như mất kết nối (tự kiểm
  // 16/09/2026 — người dùng thấy câu ấy khi vai hôm nay không có quyền thu).
  const res = await proxyJsonToBackend(
    "GET",
    `/api/v1/cashier/board?modes=${encodeURIComponent(modes)}`,
    undefined,
  );
  if (res.status === 401 || res.status === 403) {
    return NextResponse.json(
      { error: "Hôm nay bạn không đứng quầy thu ngân — không có quyền mở danh sách chờ thu." },
      { status: res.status },
    );
  }
  const d = res.ok
    ? ((await res.json()) as { items: unknown[]; paid: unknown[] })
    : null;
  if (d === null) {
    // null = không với tới backend. Trả danh sách rỗng ở đây thì quầy nói dối
    // "hôm nay không ai chờ thu", và thu ngân đóng máy đi về.
    return NextResponse.json(
      { error: "Không đọc được danh sách chờ thu" },
      { status: 502 },
    );
  }
  return NextResponse.json(d, {
    headers: { "Cache-Control": "private, no-store" },
  });
}
