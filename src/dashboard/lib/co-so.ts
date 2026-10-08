// CƠ SỞ ĐANG ĐỨNG (08/10/2026 — mở Hào Nam). Người dùng chọn sau đăng nhập
// (`/chon-co-so`), lưu ở cookie; mọi lời gọi FastAPI mang nó trong header
// `X-Location-ID`. Header chỉ là BỘ CHỌN: máy chủ kiểm cơ sở thuộc phòng khám
// và đang bật (identity.py). Không có cookie → máy chủ dùng cơ sở mặc định của
// tài khoản, y như trước khi có hai cơ sở.

import { cookies } from "next/headers";

export const LOCATION_COOKIE = "clinicai_location";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Gắn `X-Location-ID` vào `headers` nếu cookie có cơ sở hợp lệ. */
export async function ganCoSo(headers: Record<string, string>): Promise<void> {
  let v: string | undefined;
  try {
    v = (await cookies()).get(LOCATION_COOKIE)?.value;
  } catch {
    // Ngoài ngữ cảnh request (không có cookie) — không gắn gì.
    return;
  }
  if (v && UUID.test(v)) headers["X-Location-ID"] = v;
}
