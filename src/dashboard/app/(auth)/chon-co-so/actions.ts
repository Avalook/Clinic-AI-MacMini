"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { LOCATION_COOKIE } from "../../../lib/co-so";
import { duongVeAnToan } from "./duong-ve";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Ghi cơ sở đã chọn rồi đi tiếp. Không tự kiểm "cơ sở có hợp lệ không": máy
 *  chủ kiểm ở MỌI request (identity.py — cơ sở lạ/đã tắt → 403). */
export async function chonCoSo(formData: FormData): Promise<void> {
  const id = String(formData.get("co_so") ?? "");
  const next = duongVeAnToan(String(formData.get("next") ?? ""));
  if (!UUID.test(id)) redirect(`/chon-co-so?next=${encodeURIComponent(next)}`);
  (await cookies()).set(LOCATION_COOKIE, id, {
    path: "/",
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    // Cùng tuổi với cookie vai/nhân viên ở đăng nhập (12 giờ = một ngày làm).
    maxAge: 60 * 60 * 12,
  });
  redirect(next);
}
