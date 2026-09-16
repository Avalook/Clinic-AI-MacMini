/**
 * Thu ngân dịch vụ — một trong hai quầy của tài khoản thu ngân.
 *
 * Tuyền 16/09/2026: "thu ngân hiện tại bạn cho thành 1 tài khoản tên là
 * thu-ngan thôi để nó có cả node thu ngân dịch vụ và thu ngân thuốc cùng 1
 * chỗ luôn". Nên quầy được chọn bằng ĐƯỜNG DẪN, không bằng vai: một tài khoản,
 * hai mục ở thanh bên, mỗi mục một quầy.
 *
 * Thân quầy dùng lại QuayThuNgan — không có bản thứ hai để lệch nhau.
 */

import { requireNavAccess } from "@/lib/clinic-session";

import QuayThuNgan from "../../cashier/board/QuayThuNgan";

export const metadata = { title: "Thu ngân dịch vụ · ClinicAI" };
export const dynamic = "force-dynamic";

export default async function TrangThuNgan() {
  await requireNavAccess("/thu-ngan/dich-vu");
  return (
    <main className="page-in flex flex-col gap-4 p-4 lg:p-5">
      <header>
        <h1 className="text-2xl font-semibold text-ink">Thu ngân dịch vụ</h1>
        <p className="text-sm text-ink-muted">
          Khách đã khám xong, chờ trả tiền dịch vụ. Bấm “Đã nhận đủ” là ghi sổ.
        </p>
      </header>
      <QuayThuNgan quay="dich_vu" />
    </main>
  );
}
