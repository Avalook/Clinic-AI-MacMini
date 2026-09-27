// /api/loi — trang lỗi của giao diện gửi lỗi về KHO LỖI (27/09/2026).
// POST {vi_tri, kieu, thong_diep} → /api/v1/loi-trinh-duyet. Ai đăng nhập cũng
// gửi được; máy chủ che dữ liệu khách + cắt ngắn. Hỏng thì im — đây là đường
// báo lỗi, không được sinh thêm lỗi cho người dùng thấy.
import { proxyJsonToBackend } from "../../../lib/backend-proxy";

export async function POST(request: Request) {
  const b = (await request.json().catch(() => null)) as Record<string, unknown> | null;
  const chu = (v: unknown, n: number) => (typeof v === "string" ? v.slice(0, n) : "");
  return proxyJsonToBackend("POST", "/api/v1/loi-trinh-duyet", {
    vi_tri: chu(b?.vi_tri, 300).split("?")[0],
    kieu: chu(b?.kieu, 100) || "Error",
    thong_diep: chu(b?.thong_diep, 1000),
  });
}
