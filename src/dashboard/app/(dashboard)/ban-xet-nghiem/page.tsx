/**
 * BÀN XÉT NGHIỆM ĐỐI TÁC (05/11/2026, ADR-0015) — nhân viên nội bộ làm mọi bước:
 * ghi nhận thu hộ → lấy mẫu (mã ống) → tải kết quả → "Đúng người, gửi". Lego 21
 * (`partner.work`, cùng bàn cũ). Mọi luật ở máy chủ; màn chỉ hiển thị cờ.
 */

import { requireNavAccess } from "@/lib/clinic-session";

import BanXetNghiem from "./BanXetNghiem";

export const metadata = { title: "Bàn xét nghiệm đối tác · ClinicAI" };
export const dynamic = "force-dynamic";

export default async function BanXetNghiemPage() {
  await requireNavAccess("/ban-xet-nghiem");
  return (
    <main className="page-in flex min-w-0 flex-col gap-4 p-4 xl:p-6">
      <BanXetNghiem />
    </main>
  );
}
