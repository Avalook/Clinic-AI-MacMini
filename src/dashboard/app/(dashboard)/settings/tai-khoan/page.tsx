// Thiết lập tài khoản đăng nhập cho nhân viên.
//
// Tách khỏi trang Cài đặt vì hai việc khác hẳn nhau: bên kia là CẤU HÌNH PHÒNG
// KHÁM (chế độ tính năng, luật đặt lịch, sức chứa), còn đây là QUẢN TRỊ NGƯỜI
// DÙNG — tạo login, đặt lại mật khẩu, gỡ tài khoản.
//
// Gộp chung khiến người đi đổi luật đặt lịch phải cuộn qua danh sách chín nhân
// viên, và người đi đặt lại mật khẩu phải cuộn qua ba thẻ cấu hình.

import { redirect } from "next/navigation";
import Link from "next/link";

import { getSupabaseServer } from "../../../../lib/supabase-server";
import { getClinicRole } from "../../../../lib/clinic-session";
import {
  isAdminRole,
  ROLE_LABEL,
  type ClinicRole,
} from "../../../../lib/roles";
import AccountActions from "../AccountActions";

export const dynamic = "force-dynamic";

interface StaffRow {
  id: string;
  full_name: string;
  short_name: string | null;
  primary_department: string;
  employment_type: string;
  is_active: boolean;
  auth_user_id: string | null;
}

const TH = "px-4 py-2.5 font-medium";
const TD = "px-4 py-2.5";

export default async function ThietLapTaiKhoanPage() {
  const role = await getClinicRole();
  if (!isAdminRole(role)) redirect("/home");

  const supabase = await getSupabaseServer();
  const { data, error } = await supabase
    .from("staff")
    .select(
      "id, full_name, short_name, primary_department, employment_type, " +
        "is_active, auth_user_id",
    )
    .order("primary_department", { ascending: true })
    .order("full_name", { ascending: true });

  const rows = (data as StaffRow[] | null) ?? [];
  const linked = rows.filter((r) => r.auth_user_id !== null).length;

  return (
    <main className="page-in min-w-0 space-y-4 p-4 lg:p-5">
      <div className="flex justify-end">
        <Link
          href="/settings/new-user"
          className="rounded-control bg-brand-600 px-4 py-2 text-sm font-medium text-surface transition-colors duration-150 hover:bg-brand-700"
        >
          + Thêm tài khoản
        </Link>
      </div>

      {/* Thông báo tổng quan về trạng thái link tài khoản */}
      <div className="rounded-card border border-line bg-brand-50 px-4 py-3 text-sm text-ink-soft shadow-card">
        <span className="font-medium text-ink">{linked}</span> /{" "}
        <span className="font-medium text-ink">{rows.length}</span> nhân viên đã
        được link với tài khoản đăng nhập. Bấm{" "}
        <span className="font-medium text-ink">+ Thêm tài khoản</span> để tạo
        login mới, hoặc dùng nút thao tác ở mỗi dòng để đặt lại mật khẩu / gỡ
        tài khoản — tất cả ngay trong dashboard, không cần vào console Supabase.
      </div>

      {/* Danh sách rỗng vì LỖI khác hẳn danh sách rỗng vì chưa có ai — không
          nuốt lỗi truy vấn thành "Chưa có nhân viên." */}
      {error && (
        <div className="rounded-card border border-danger bg-danger-bg px-4 py-3 text-sm text-danger">
          {error.message}
        </div>
      )}

      {/* Điện thoại: danh sách thẻ (&lt;md). */}
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
                  {ROLE_LABEL[r.primary_department as ClinicRole] ??
                    r.primary_department}
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
                <span className="shrink-0 text-xs text-ink-muted">
                  Inactive
                </span>
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
          <thead className="sticky top-0 z-10 bg-brand-100 text-left text-label font-semibold uppercase tracking-wide text-brand-800">
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
                  {ROLE_LABEL[r.primary_department as ClinicRole] ??
                    r.primary_department}
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
                <td
                  colSpan={6}
                  className="px-4 py-6 text-center text-ink-muted"
                >
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
