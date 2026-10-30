/**
 * TÀI KHOẢN NHẬN CHUYỂN KHOẢN (31/10/2026) — Quản lý thêm / sửa / tắt tài khoản
 * ngân hàng mà quầy thu chọn khi khách chuyển khoản. Lego 18 Cài đặt phòng khám
 * (`config.clinic.manage`); máy chủ hỏi lại ở mọi lệnh ghi.
 */

import { requireNavAccess } from "@/lib/clinic-session";
import { layCoSo } from "@/lib/danh-muc";

import TaiKhoanNhanView from "./TaiKhoanNhanView";

export const metadata = { title: "Tài khoản nhận chuyển khoản · ClinicAI" };
export const dynamic = "force-dynamic";

export default async function TaiKhoanNhanPage() {
  await requireNavAccess("/settings/tai-khoan-nhan");
  const coSo = await layCoSo();
  return (
    <main className="page-in flex min-w-0 flex-col gap-4 p-4 xl:p-6">
      <TaiKhoanNhanView coSo={coSo} />
    </main>
  );
}
