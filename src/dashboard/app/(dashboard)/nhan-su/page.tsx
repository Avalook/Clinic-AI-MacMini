// Hồ sơ nhân sự — dựng từ bản mockup quan-ly-nhan-su.html.
//
// KHÁC VỚI /settings/clinic-config. Màn kia gán nhân viên vào TRẠM CÔNG VIỆC
// (ai đứng ở phòng nào); màn này là HỒ SƠ con người (tên, vai, cơ sở, loại hợp
// đồng, đang làm hay đã nghỉ). Hai việc khác nhau nên hai trang khác nhau.
//
// PHẦN MOCKUP CHƯA DỰNG ĐƯỢC, VÀ VÌ SAO. Bản mockup có ngày sinh, giới tính,
// CCCD + ngày cấp, SĐT, email, số CCHN + ngày cấp, phạm vi hoạt động chuyên
// môn, tài liệu đính kèm — bảng `staff` không có cột nào trong số đó. Trang này
// hiện chúng thành ô mờ có nhãn "chưa lưu được" thay vì vẽ ô trống trông như
// dùng được: một ô nhập gõ vào rồi mất là tệ hơn một ô nói thẳng là chưa có.
//
// CCCD là định danh công dân. Thêm cột cho nó là một quyết định riêng — ai được
// đọc (RLS), giữ bao lâu, có che bớt trên màn hình không — không phải việc gắn
// thêm một cột vì mockup có vẽ.

import { requireNavAccess } from "../../../lib/clinic-session";
import { fetchFromBackend } from "../../../lib/backend-proxy";
import NhanSuBoard from "./NhanSuBoard";
import type { StaffRow } from "../../api/staff/route";

export const dynamic = "force-dynamic";

interface ConfigLocation {
  id: string;
  name: string;
}

export default async function NhanSuPage() {
  await requireNavAccess("/nhan-su");

  const [staff, overview] = await Promise.all([
    fetchFromBackend<StaffRow[]>("/api/v1/staff"),
    fetchFromBackend<{ locations: ConfigLocation[] }>(
      "/api/v1/clinic-config/overview",
    ),
  ]);

  return (
    <main className="page-in min-w-0 space-y-5 p-4 lg:p-5">
      <header>
        <h1 className="text-xl font-semibold text-ink lg:text-2xl">
          Quản lý nhân sự
        </h1>
        <p className="mt-1 text-sm text-ink-muted">
          Hồ sơ từng người: vai trò, cơ sở làm việc, loại hợp đồng, đang làm hay
          đã nghỉ. Muốn gán ai đứng phòng nào thì vào{" "}
          <span className="font-medium text-ink">Cấu trúc phòng khám</span>.
        </p>
      </header>

      <NhanSuBoard
        initialStaff={staff ?? []}
        locations={overview?.locations ?? []}
      />
    </main>
  );
}
