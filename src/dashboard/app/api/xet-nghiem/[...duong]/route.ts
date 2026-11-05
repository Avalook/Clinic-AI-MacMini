// Bàn xét nghiệm đối tác đời mới (ADR-0015) — proxy mỏng sang FastAPI `/api/v1/xet-nghiem/*`.
//
// Danh sách trắng (method + mẫu đường): một `[...duong]` trần sẽ mở luôn cả những
// đường thêm sau này mà chưa ai cân nhắc có nên cho trình duyệt gọi không. Tầng này
// chỉ kiểm HÌNH của mã; quyền, luật, câu lỗi đều ở máy chủ.

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

type Method = "GET" | "POST" | "PUT";

const U = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}";

const LENH_BAN = "ghi-thu|huy-thu|hoan-tien|lay-mau|huy-mau|sua-hen-tra|cho-qua|go-cho-qua|dong|mo-lai|gui|thu-hoi";

/** [method, mẫu đường sau /xet-nghiem/, đường backend VIẾT RÕ] — thêm cửa = thêm một
 *  dòng. Đường backend viết hẳn ra để test `test_dashboard_backend_paths` đối chiếu
 *  được với router thật. */
const CHO_PHEP: [Method, RegExp, (m: RegExpMatchArray) => string][] = [
  // Cài đặt → Đối tác (chặng 1)
  ["GET", /^doi-tac$/, () => "/api/v1/xet-nghiem/doi-tac"],
  ["POST", /^doi-tac$/, () => "/api/v1/xet-nghiem/doi-tac"],
  ["PUT", new RegExp(`^doi-tac/(${U})$`, "i"), (m) => `/api/v1/xet-nghiem/doi-tac/${m[1]}`],
  ["POST", new RegExp(`^doi-tac/(${U})/ngung$`, "i"), (m) => `/api/v1/xet-nghiem/doi-tac/${m[1]}/ngung`],
  ["POST", /^doi-tac-dich-vu$/, () => "/api/v1/xet-nghiem/doi-tac-dich-vu"],
  [
    "POST",
    new RegExp(`^doi-tac-dich-vu/(${U})/bo$`, "i"),
    (m) => `/api/v1/xet-nghiem/doi-tac-dich-vu/${m[1]}/bo`,
  ],
  ["PUT", /^cai-dat$/, () => "/api/v1/xet-nghiem/cai-dat"],
  // Bàn xét nghiệm (chặng 2–3)
  ["GET", /^ban$/, () => "/api/v1/xet-nghiem/ban"],
  ["GET", /^ban\/tien$/, () => "/api/v1/xet-nghiem/ban/tien"],
  ["GET", /^ban\/qua-trinh$/, () => "/api/v1/xet-nghiem/ban/qua-trinh"],
  ["POST", new RegExp(`^ban/(${LENH_BAN})$`), (m) => `/api/v1/xet-nghiem/ban/${m[1]}`],
];

function sai(message: string, status = 400) {
  return NextResponse.json({ error: "BAD_REQUEST", message }, { status });
}

async function chuyen(method: Method, request: Request, ctx: { params: Promise<{ duong: string[] }> }) {
  const duong = (await ctx.params).duong.join("/");
  let dich: string | null = null;
  for (const [m, re, toi] of CHO_PHEP) {
    const k = m === method ? duong.match(re) : null;
    if (k) {
      dich = toi(k);
      break;
    }
  }
  if (!dich) return sai("Đường không hợp lệ.", 404);
  if (method === "GET") return proxyJsonToBackend("GET", `${dich}${new URL(request.url).search}`, undefined);
  let body: unknown = {};
  try {
    body = await request.json();
  } catch {
    body = {};
  }
  return proxyJsonToBackend(method, dich, body);
}

export const GET = (r: Request, c: { params: Promise<{ duong: string[] }> }) => chuyen("GET", r, c);
export const POST = (r: Request, c: { params: Promise<{ duong: string[] }> }) => chuyen("POST", r, c);
export const PUT = (r: Request, c: { params: Promise<{ duong: string[] }> }) => chuyen("PUT", r, c);
