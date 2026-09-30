// Dọn dữ liệu khách thử (Tuyền chốt 30/09/2026): quản trị viên xem khách theo
// NGÀY như màn Tiếp đón, tick từng khách, xem trước số dòng, gõ XOA để xoá.
//
// Cửa màn theo lego "Nhân sự & phân quyền" (`permission.manage`); máy chủ hỏi
// lại `permission.manage` ở MỌI lệnh — trang này không tự quyết ai được xoá.

import { fetchFromBackend } from "../../../../lib/backend-proxy";
import { requireNavAccess } from "../../../../lib/clinic-session";
import DonDuLieuThu, { type DuLieuNgay } from "./DonDuLieuThu";

export const dynamic = "force-dynamic";

export default async function DonDuLieuThuPage({
  searchParams,
}: {
  searchParams: Promise<{ ngay?: string }>;
}) {
  await requireNavAccess("/settings/don-du-lieu-thu");
  const { ngay } = await searchParams;
  // Ngày sai hình → gửi rỗng; máy chủ hiểu rỗng/rác là hôm qua.
  const d = ngay && /^\d{4}-\d{2}-\d{2}$/.test(ngay) ? ngay : "";
  const duLieu = await fetchFromBackend<DuLieuNgay>(`/api/v1/quan-tri/don-du-lieu-thu?ngay=${d}`);

  return (
    <main className="page-in min-w-0 space-y-4 p-4 lg:p-5">
      {duLieu ? (
        <DonDuLieuThu banDau={duLieu} />
      ) : (
        <p className="rounded-card bg-warning-bg px-4 py-3 text-body text-warning">
          Không đọc được danh sách — tài khoản cần quyền Phân quyền (quản trị cao nhất).
        </p>
      )}
    </main>
  );
}
