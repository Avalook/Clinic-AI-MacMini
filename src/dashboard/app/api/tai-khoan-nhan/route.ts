// Tài khoản ngân hàng nhận chuyển khoản (31/10/2026) — proxy mỏng sang FastAPI.
//
//   GET  /api/tai-khoan-nhan?visit_id=…  → danh mục + tài khoản dùng được / mặc
//        định ở cơ sở của lượt (không visit_id = cơ sở đang đăng nhập)
//   POST { ten_goi, ngan_hang, so_tai_khoan, chu_tai_khoan, location_id, mac_dinh, dang_dung }
//        → thêm; kèm `id` → sửa / bật / tắt / đặt mặc định
//
// Tầng này chỉ kiểm HÌNH của mã. Quyền (lego Cài đặt phòng khám), luật mặc định
// và "tắt chứ không xoá" ở máy chủ.

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "../../../lib/backend-proxy";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function sai(message: string) {
  return NextResponse.json({ error: "BAD_REQUEST", message }, { status: 400 });
}

export async function GET(request: Request) {
  const v = new URL(request.url).searchParams.get("visit_id") ?? "";
  if (v && !UUID_RE.test(v)) return sai("Lượt khám không hợp lệ.");
  return v
    ? proxyJsonToBackend("GET", `/api/v1/tai-khoan-nhan?visit_id=${encodeURIComponent(v)}`, undefined)
    : proxyJsonToBackend("GET", "/api/v1/tai-khoan-nhan", undefined);
}

export async function POST(request: Request) {
  let b: Record<string, unknown>;
  try {
    b = (await request.json()) as Record<string, unknown>;
  } catch {
    return sai("Dữ liệu gửi lên không đọc được.");
  }
  const id = typeof b.id === "string" ? b.id : "";
  if (id && !UUID_RE.test(id)) return sai("Tài khoản không hợp lệ.");
  const than = {
    ten_goi: b.ten_goi,
    ngan_hang: b.ngan_hang,
    so_tai_khoan: b.so_tai_khoan,
    chu_tai_khoan: b.chu_tai_khoan,
    location_id: b.location_id ?? null,
    mac_dinh: b.mac_dinh === true,
    dang_dung: b.dang_dung !== false,
  };
  return id
    ? proxyJsonToBackend("PUT", `/api/v1/tai-khoan-nhan/${id}`, than)
    : proxyJsonToBackend("POST", "/api/v1/tai-khoan-nhan", than);
}
