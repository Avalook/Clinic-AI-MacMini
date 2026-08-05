// Settings — Admin-only staff overview. The current Phase 1 demo need
// is for an operator to see which staff rows are linked to a Supabase
// Auth account (the green dot) so they can run
// ``scripts/seed/link_staff_to_auth.py`` for the missing ones.
// Cài đặt — Tổng quan nhân viên chỉ dành cho Admin. Nhu cầu demo Phase 1 hiện tại
// là để người vận hành thấy dòng nhân viên nào đã được link với tài khoản
// Supabase Auth (chấm xanh) để họ có thể chạy
// ``scripts/seed/link_staff_to_auth.py`` cho những người còn thiếu.

// Nhập component Link từ Next.js để tạo liên kết nội bộ
import Link from "next/link";
// Nhập hàm redirect từ Next.js để chuyển hướng
import { redirect } from "next/navigation";
// Nhập hàm getSupabaseServer để lấy client Supabase phía server
import { getSupabaseServer } from "../../../lib/supabase-server";
// Nhập hàm getClinicRole để lấy vai trò phòng khám
import { getClinicRole } from "../../../lib/clinic-session";
// Nhập các hàm và kiểu dữ liệu liên quan đến vai trò
import { isAdminRole, ROLE_LABEL, type ClinicRole } from "../../../lib/roles";
// Nhập hàm getBookingPolicy để lấy luật đặt lịch
import { getBookingPolicy } from "../../../lib/booking-policy";
// Nhập component AccountActions để quản lý tài khoản
import AccountActions from "./AccountActions";
// Nhập component BookingPolicyCard để hiển thị luật đặt lịch
import BookingPolicyCard from "./BookingPolicyCard";
// Nhập component FeatureModeCard để hiển thị chế độ tính năng
import FeatureModeCard from "./FeatureModeCard";
// Nhập hàm getFeatureMode để lấy chế độ tính năng
import { getFeatureMode } from "../../../lib/feature-mode";

// Ép Next.js render trang này động (không cache) — luôn lấy dữ liệu mới nhất
export const dynamic = "force-dynamic";

// Định nghĩa interface cho một dòng nhân viên
interface StaffRow {
  id: string; // ID nhân viên
  full_name: string; // Tên đầy đủ
  short_name: string | null; // Tên viết tắt, có thể null
  primary_department: string; // Phòng ban chính
  employment_type: string; // Loại hợp đồng
  is_active: boolean; // Có đang hoạt động không
  auth_user_id: string | null; // ID người dùng xác thực, có thể null
}

// Friendly label per Supabase CHECK enum.
// Nhãn vai dùng ROLE_LABEL của lib/roles.ts. Trước đây file này (và
// settings/page.tsx) mỗi nơi giữ một bản DEPT_LABEL riêng, và CẢ HAI đều
// thiếu PHARMACIST — vai đã chạy từ khi có màn /pharmacy. Hệ quả: màn tạo
// user và màn danh sách nhân viên hiện chữ "PHARMACIST" thô cho dược sĩ.
// Cùng một lỗi đã xảy ra ở ROLE_VI trong WorkItemActions.tsx: một bảng nhãn
// chép tay là một bảng nhãn sẽ thiếu vai tiếp theo.

// Style cho ô tiêu đề bảng
const TH = "px-4 py-2.5 font-medium";
// Style cho ô dữ liệu bảng
const TD = "px-4 py-2.5";

// Component chính của trang cài đặt (server component)
export default async function SettingsPage() {
  // Lấy vai trò phòng khám của người dùng
  const role = await getClinicRole();
  // Nếu không phải vai trò admin thì chuyển hướng về trang chủ
  if (!isAdminRole(role)) redirect("/home");

  // Lấy client Supabase phía server (dùng cookie phiên đăng nhập)
  const supabase = await getSupabaseServer();
  // Truy vấn danh sách nhân viên từ Supabase
  const { data, error } = await supabase
    .from("staff") // Từ bảng staff (nhân viên)
    .select(
      // Chọn các cột cần thiết
      "id, full_name, short_name, primary_department, employment_type, " +
        "is_active, auth_user_id",
    )
    .order("primary_department", { ascending: true }) // Sắp xếp theo phòng ban tăng dần
    .order("full_name", { ascending: true }); // Sắp xếp theo tên tăng dần

  // Luật đặt lịch của phòng khám — hiển thị + cho phép Trưởng ca/Quản lý sửa.
  // Lấy luật đặt lịch hiện tại
  const bookingPolicy = await getBookingPolicy();

  // Ép kiểu dữ liệu nhân viên, nếu null thì dùng mảng rỗng
  const rows = (data as StaffRow[] | null) ?? [];
  // Đếm số nhân viên đã link với tài khoản đăng nhập
  const linked = rows.filter((r) => r.auth_user_id !== null).length;
  // Lấy chế độ tính năng hiện tại
  const featureMode = await getFeatureMode();

  return (
    // Container chính của trang
    <main className="page-in min-w-0 space-y-5 p-4 lg:p-5">
      {/* Phần đầu trang */}
      <header className="flex flex-wrap items-start justify-between gap-3">
        {/* Tiêu đề và mô tả */}
        <div className="min-w-0">
          <h1 className="text-xl font-semibold text-ink lg:text-2xl">Cài đặt tài khoản</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Nhân viên + trạng thái liên kết tài khoản đăng nhập.
          </p>
        </div>
        {/* Nút thêm tài khoản mới */}
        <Link
          href="/settings/new-user"
          className="shrink-0 rounded-control bg-brand-600 px-4 py-2 text-sm font-medium text-surface transition-colors duration-150 hover:bg-brand-700"
        >
          + Thêm tài khoản
        </Link>
      </header>

      {/* Thông báo tổng quan về trạng thái link tài khoản */}
      <div className="rounded-card border border-line bg-brand-50 px-4 py-3 text-sm text-ink-soft shadow-card">
        <span className="font-medium text-ink">{linked}</span> /{" "}
        <span className="font-medium text-ink">{rows.length}</span>{" "}
        nhân viên đã được link với tài khoản đăng nhập. Bấm{" "}
        <span className="font-medium text-ink">+ Thêm tài khoản</span>{" "}
        để tạo login mới, hoặc dùng nút thao tác ở mỗi dòng để đặt lại mật
        khẩu / gỡ tài khoản — tất cả ngay trong dashboard, không cần vào
        console Supabase.
      </div>

      {/* Card chế độ tính năng */}
      <FeatureModeCard currentMode={featureMode} />

      {/* Card luật đặt lịch */}
      <BookingPolicyCard policy={bookingPolicy} />

      {/* Nếu có lỗi khi truy vấn */}
      {error && (
        // Hiển thị thông báo lỗi màu đỏ
        <div className="rounded-card border border-danger bg-danger-bg px-4 py-3 text-sm text-danger">
          {error.message}
        </div>
      )}

      {/* Mobile: card list (<md). */}
      {/* Danh sách dạng card cho màn hình di động */}
      <ul className="space-y-2 md:hidden">
        {/* Lặp qua từng nhân viên */}
        {rows.map((r) => (
          <li
            key={r.id} // Key duy nhất
            className="rounded-card border border-line bg-surface p-4 shadow-card"
          >
            {/* Phần đầu: tên + vai trò + trạng thái */}
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                {/* Tên nhân viên */}
                <p className="font-medium text-ink">{r.full_name}</p>
                {/* Vai trò + loại hợp đồng */}
                <p className="text-xs text-ink-muted">
                  {ROLE_LABEL[r.primary_department as ClinicRole] ?? r.primary_department}
                  {" · "}
                  <span className="text-ink-muted">{r.employment_type}</span>
                </p>
              </div>
              {/* Trạng thái active/inactive */}
              {r.is_active ? (
                <span className="inline-flex shrink-0 items-center gap-1 text-xs text-success">
                  <span className="h-1.5 w-1.5 rounded-full bg-success" />
                  Active
                </span>
              ) : (
                <span className="shrink-0 text-xs text-ink-muted">Inactive</span>
              )}
            </div>
            {/* Phần dưới: trạng thái link + nút thao tác */}
            <div className="mt-2 flex items-center justify-between gap-2">
              {/* Trạng thái đã link/chưa link */}
              {r.auth_user_id ? (
                <span className="inline-flex items-center gap-1 text-xs text-success">
                  <span className="h-1.5 w-1.5 rounded-full bg-success" />
                  Đã link
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-xs text-warning">
                  <span className="h-1.5 w-1.5 rounded-full bg-warning" />
                  Chưa link
                </span>
              )}
              {/* Nút thao tác: quản lý tài khoản hoặc tạo tài khoản */}
              {r.auth_user_id ? (
                <AccountActions staffId={r.id} staffName={r.full_name} />
              ) : (
                <Link
                  href="/settings/new-user"
                  className="text-xs text-brand-600 hover:underline"
                >
                  Tạo tài khoản
                </Link>
              )}
            </div>
          </li>
        ))}
        {/* Nếu không có nhân viên nào */}
        {rows.length === 0 && (
          <li className="rounded-card border border-line bg-surface px-4 py-8 text-center text-sm text-ink-muted shadow-card">
            Chưa có nhân viên.
          </li>
        )}
      </ul>

      {/* Desktop: table (≥md). */}
      {/* Bảng danh sách nhân viên cho màn hình desktop */}
      <div className="hidden min-h-[180px] max-h-[88vh] overflow-x-auto overflow-y-auto rounded-card border border-line bg-surface shadow-card md:block">
        <table className="min-w-full divide-y divide-brand-100 text-sm">
          {/* Tiêu đề bảng, cố định khi cuộn */}
          <thead className="sticky top-0 z-10 bg-brand-100 text-left text-[11px] font-semibold uppercase tracking-wide text-brand-800">
            <tr>
              <th className={TH}>Họ tên</th> {/* Cột họ tên */}
              <th className={TH}>Vai trò</th> {/* Cột vai trò */}
              <th className={TH}>Hợp đồng</th> {/* Cột hợp đồng */}
              <th className={TH}>Active</th> {/* Cột trạng thái active */}
              <th className={TH}>Login</th> {/* Cột trạng thái login */}
              <th className={TH}>Thao tác</th> {/* Cột thao tác */}
            </tr>
          </thead>
          {/* Thân bảng */}
          <tbody className="divide-y divide-brand-100">
            {/* Lặp qua từng nhân viên */}
            {rows.map((r) => (
              <tr
                key={r.id} // Key duy nhất
                className="transition-colors duration-150 hover:bg-brand-50"
              >
                {/* Cột họ tên */}
                <td className={`${TD} text-ink`}>
                  {r.full_name}
                  {/* Tên viết tắt nếu khác tên đầy đủ */}
                  {r.short_name && r.short_name !== r.full_name && (
                    <span className="ml-2 text-xs text-ink-muted">
                      {r.short_name}
                    </span>
                  )}
                </td>
                {/* Cột vai trò */}
                <td className={`${TD} text-ink-soft`}>
                  {ROLE_LABEL[r.primary_department as ClinicRole] ?? r.primary_department}
                </td>
                {/* Cột loại hợp đồng */}
                <td className={`${TD} text-xs text-ink-muted`}>
                  {r.employment_type}
                </td>
                {/* Cột trạng thái active */}
                <td className={TD}>
                  {r.is_active ? (
                    <span className="inline-flex items-center gap-1 text-xs text-success">
                      <span className="h-1.5 w-1.5 rounded-full bg-success" />
                      Active
                    </span>
                  ) : (
                    <span className="text-xs text-ink-muted">Inactive</span>
                  )}
                </td>
                {/* Cột trạng thái login */}
                <td className={TD}>
                  {r.auth_user_id ? (
                    <span className="inline-flex items-center gap-1 text-xs text-success">
                      <span className="h-1.5 w-1.5 rounded-full bg-success" />
                      Đã link
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-xs text-warning">
                      <span className="h-1.5 w-1.5 rounded-full bg-warning" />
                      Chưa link
                    </span>
                  )}
                </td>
                {/* Cột thao tác */}
                <td className={TD}>
                  {r.auth_user_id ? (
                    <AccountActions staffId={r.id} staffName={r.full_name} />
                  ) : (
                    <Link
                      href="/settings/new-user"
                      className="text-xs text-brand-600 hover:underline"
                    >
                      Tạo tài khoản
                    </Link>
                  )}
                </td>
              </tr>
            ))}
            {/* Nếu không có nhân viên nào */}
            {rows.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-ink-muted">
                  Chưa có nhân viên.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </main>
  );
}