// Cài đặt phòng khám — chỉ CẤU HÌNH: chế độ tính năng và luật đặt lịch.
//
// Danh sách tài khoản đăng nhập của nhân viên đã tách sang mục riêng
// `/settings/tai-khoan` ("Thiết lập tài khoản cho nhân viên"). Hai việc khác
// hẳn nhau: đây là cấu hình phòng khám, bên kia là quản trị người dùng — gộp
// chung thì người đi đổi luật đặt lịch phải cuộn qua danh sách nhân viên, và
// người đi đặt lại mật khẩu phải cuộn qua các thẻ cấu hình.

import { redirect } from "next/navigation";

import { getClinicRole } from "../../../lib/clinic-session";
import { isAdminRole } from "../../../lib/roles";
import { getBookingPolicy } from "../../../lib/booking-policy";
import { getFeatureMode } from "../../../lib/feature-mode";
import BookingPolicyCard from "./BookingPolicyCard";
import FeatureModeCard from "./FeatureModeCard";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const role = await getClinicRole();
  if (!isAdminRole(role)) redirect("/home");

  const bookingPolicy = await getBookingPolicy();
  const featureMode = await getFeatureMode();

  return (
    <main className="page-in min-w-0 space-y-5 p-4 lg:p-5">
      {/* Tiêu đề nằm ở thanh trên cùng (GlobalHeader) — không lặp lại ở đây. */}
      <FeatureModeCard currentMode={featureMode} />
      <BookingPolicyCard policy={bookingPolicy} />
    </main>
  );
}
