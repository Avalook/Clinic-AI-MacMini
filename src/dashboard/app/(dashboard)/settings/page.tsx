// Cài đặt phòng khám — chỉ CẤU HÌNH: chế độ tính năng và luật đặt lịch.
//
// Danh sách tài khoản đăng nhập của nhân viên đã tách sang mục riêng
// `/settings/tai-khoan` ("Thiết lập tài khoản cho nhân viên"). Hai việc khác
// hẳn nhau: đây là cấu hình phòng khám, bên kia là quản trị người dùng — gộp
// chung thì người đi đổi luật đặt lịch phải cuộn qua danh sách nhân viên, và
// người đi đặt lại mật khẩu phải cuộn qua các thẻ cấu hình.


import { getViTriHomNay, requireNavAccess } from "../../../lib/clinic-session";
import { viTriTuDb } from "../../../lib/roster";
import { getBookingPolicy } from "../../../lib/booking-policy";
import { getFeatureMode } from "../../../lib/feature-mode";
import BookingPolicyCard from "./BookingPolicyCard";
import FeatureModeCard from "./FeatureModeCard";
import PhamViViTriCard, { type OViTri } from "./PhamViViTriCard";
import { fetchFromBackend } from "../../../lib/backend-proxy";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  // Lego 18 "Cài đặt phòng khám" (27/09/2026) — trước gác vai Quản lý.
  await requireNavAccess("/settings");

  const bookingPolicy = await getBookingPolicy();
  const featureMode = await getFeatureMode();
  // Đọc SERVER-SIDE rồi truyền xuống làm prop. Nạp trong useEffect thì trình
  // biên dịch React chặn setState đồng bộ trong effect — đã vấp ba lần.
  const [phamVi, viTri] = await Promise.all([
    fetchFromBackend<{ items: OViTri[] }>("/api/v1/roster/station-scope"),
    getViTriHomNay(),
  ]);
  const danhMuc = viTriTuDb(viTri?.danh_muc);

  return (
    <main className="page-in min-w-0 space-y-5 p-4 lg:p-5">
      {/* Tiêu đề nằm ở thanh trên cùng (GlobalHeader) — không lặp lại ở đây. */}
      <FeatureModeCard currentMode={featureMode} />
      <BookingPolicyCard policy={bookingPolicy} />
      {phamVi && (
        <PhamViViTriCard
          items={phamVi.items}
          stations={danhMuc}
        />
      )}
    </main>
  );
}
