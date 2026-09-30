// PHÂN QUYỀN — màn của quản lý, nơi "ai làm được gì" thôi phụ thuộc vào người
// sửa code.
//
// Mô hình chốt trong chat (#124, #132, #133, #134): tài khoản là CON NGƯỜI, vai
// chỉ là preset để cấp cho nhanh, quyền thật là capability gom theo KHỐI CÔNG
// VIỆC. Quản lý bật/tắt cả khối; "▾ Chi tiết" mới bung quyền con.
//
// Trang này không giữ luật nào. Ai được cấp quyền cho ai là capability
// `permission.manage`, backend kiểm trong chính giao dịch của lệnh.

import { fetchFromBackend } from "../../../lib/backend-proxy";
import { requireNavAccess } from "../../../lib/clinic-session";
import type { StaffRow } from "../../api/staff/route";
import BangPhanQuyen from "./BangPhanQuyen";

export const dynamic = "force-dynamic";
export const metadata = { title: "Phân quyền · ClinicAI" };

export default async function TrangPhanQuyen({
  searchParams,
}: {
  searchParams: Promise<{ nguoi?: string }>;
}) {
  // `?nguoi=` — mở thẳng từ hồ sơ nhân sự (màn Nhân sự thôi quản quyền 23/09).
  const { nguoi } = await searchParams;
  await requireNavAccess("/phan-quyen");
  const nhanSu = (await fetchFromBackend<StaffRow[]>("/api/v1/staff")) ?? [];
  return (
    <main className="page-in flex flex-col gap-4 p-4 lg:p-5">
      <header>
        <h1 className="text-2xl font-semibold text-ink">Phân quyền</h1>
        <p className="text-sm text-ink-muted">
          Chọn một người rồi tick những kỹ năng họ làm — đúng như danh sách nhân
          sự của phòng khám. Trường hợp đặc biệt thì mở mục Ngoại lệ.
        </p>
        {/* Mở full lego (Tuyền 30/09/2026) — migration 20260930900000. */}
        <p
          role="note"
          className="mt-2 rounded-control bg-info-bg px-3 py-2 text-sm text-info"
        >
          Đang mở toàn bộ cho mọi nhân sự: ai cũng có đủ các lego thao tác (thu
          tiền dịch vụ và thuốc, khám, phòng dịch vụ, kho, điều phối, báo cáo…) và
          không cần có lịch. Chỉ Quản lý giữ Phân quyền, Nhân sự &amp; tài khoản,
          Cài đặt phòng khám (gồm mẫu kết quả, dây nối). Muốn siết một người: tắt
          lego của người ấy ở đây.
        </p>
      </header>
      <BangPhanQuyen
        nhanSu={nhanSu
          .filter((n) => n.is_active)
          .map((n) => ({
            id: n.id,
            ten: n.full_name,
            vai: n.primary_department,
          }))}
      chonTruoc={nguoi} />
    </main>
  );
}
