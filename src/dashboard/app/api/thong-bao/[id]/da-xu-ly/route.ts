// ĐÓNG MỘT VIỆC trong chuông — khác hẳn "đánh dấu đã đọc".
//
// `da_doc_luc` chỉ tắt chấm đỏ; `da_xu_ly_luc` mới lấy dòng ấy ra khỏi hàng đợi
// (`cua_toi()` lọc `da_xu_ly_luc IS NULL`). Cho tới 10/08/2026 backend đã có
// đủ endpoint và service, còn frontend KHÔNG có một người gọi nào — nên mọi
// thông báo từng sinh ra đều nằm lại trong chuông vĩnh viễn, và cái chuông
// trượt dần thành một danh sách không ai đọc.
//
//   POST { ghi_chu? } → đóng việc, trả về thời gian phản hồi tính bằng giây

import { NextResponse } from "next/server";
import { proxyJsonToBackend } from "../../../../../lib/backend-proxy";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const thongBaoId = (id ?? "").trim();
  if (!thongBaoId) {
    return NextResponse.json({ error: "Thiếu id thông báo." }, { status: 400 });
  }
  // Thân rỗng là hợp lệ: `ghi_chu` không bắt buộc, và nút trên chuông không hỏi
  // chữ nào. Gói trong try để một thân rỗng không thành lỗi 400 khó hiểu.
  let body: unknown = {};
  try {
    body = await request.json();
  } catch {
    body = {};
  }
  return proxyJsonToBackend(
    "POST",
    `/api/v1/thong-bao/${encodeURIComponent(thongBaoId)}/da-xu-ly`,
    body,
  );
}
