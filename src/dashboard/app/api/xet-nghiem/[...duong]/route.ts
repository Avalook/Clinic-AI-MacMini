// Bàn xét nghiệm đối tác đời mới (ADR-0015) — proxy mỏng sang FastAPI `/api/v1/xet-nghiem/*`.
//
// Danh sách trắng (method + mẫu đường): một `[...duong]` trần sẽ mở luôn cả những
// đường thêm sau này mà chưa ai cân nhắc có nên cho trình duyệt gọi không. Tầng này
// chỉ kiểm HÌNH của mã; quyền, luật, câu lỗi đều ở máy chủ.

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

type Method = "GET" | "POST" | "PUT";

const U = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}";

/** [method, mẫu đường sau /xet-nghiem/] — thêm cửa mới = thêm một dòng ở đây. */
const CHO_PHEP: [Method, RegExp][] = [
  // Cài đặt → Đối tác (chặng 1)
  ["GET", /^doi-tac$/],
  ["POST", /^doi-tac$/],
  ["PUT", new RegExp(`^doi-tac/${U}$`, "i")],
  ["POST", new RegExp(`^doi-tac/${U}/ngung$`, "i")],
  ["POST", /^doi-tac-dich-vu$/],
  ["POST", new RegExp(`^doi-tac-dich-vu/${U}/bo$`, "i")],
  ["PUT", /^cai-dat$/],
  // Bàn xét nghiệm (chặng 2–3)
  ["GET", /^ban$/],
  ["GET", /^ban\/tien$/],
  [
    "POST",
    /^ban\/(ghi-thu|huy-thu|hoan-tien|lay-mau|huy-mau|sua-hen-tra|cho-qua|go-cho-qua|dong|mo-lai|gui|thu-hoi)$/,
  ],
];

function sai(message: string, status = 400) {
  return NextResponse.json({ error: "BAD_REQUEST", message }, { status });
}

async function chuyen(method: Method, request: Request, ctx: { params: Promise<{ duong: string[] }> }) {
  const duong = (await ctx.params).duong.join("/");
  if (!CHO_PHEP.some(([m, re]) => m === method && re.test(duong))) {
    return sai("Đường không hợp lệ.", 404);
  }
  const q = new URL(request.url).search;
  if (method === "GET") return proxyJsonToBackend("GET", `/api/v1/xet-nghiem/${duong}${q}`, undefined);
  let body: unknown = {};
  try {
    body = await request.json();
  } catch {
    body = {};
  }
  return proxyJsonToBackend(method, `/api/v1/xet-nghiem/${duong}`, body);
}

export const GET = (r: Request, c: { params: Promise<{ duong: string[] }> }) => chuyen("GET", r, c);
export const POST = (r: Request, c: { params: Promise<{ duong: string[] }> }) => chuyen("POST", r, c);
export const PUT = (r: Request, c: { params: Promise<{ duong: string[] }> }) => chuyen("PUT", r, c);
