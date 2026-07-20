"use client";

// Desktop sidebar nav links + the drawer's link list. Visibility is per-role
// (see canSeeNav). Client component so it can highlight the active route.

import Link from "next/link";
import { usePathname } from "next/navigation";
import { canSeeNav, type ClinicRole } from "../../lib/roles";
import { NAV, isActiveNav, navLabelFor } from "./nav-items";
import { useNotifications } from "./NotificationContext";

export default function Nav({
  role,
  onNavigate,
  isCollapsed = false,
}: {
  role: ClinicRole | null;
  /** Called after a nav item is tapped (used to close the mobile drawer). */
  onNavigate?: () => void;
  isCollapsed?: boolean;
}) {
  const pathname = usePathname();
  // Đang ở trang KHÁC mà có thông báo lịch chưa xem → nhấp nháy "!" ở mục Trang chủ
  // (chuông chỉ nằm ở Trang chủ; đây là tín hiệu nhắc người dùng quay về xem).
  const { unread } = useNotifications();
  const blinkHome = unread > 0 && pathname !== "/home";
  const visible = NAV.filter((item) => canSeeNav(role, item.href));
  const hrefs = visible.map((v) => v.href);

  return (
    <nav className="space-y-0.5">
      {visible.map((item) => {
        const { href, badge, icon: Icon } = item;
        const active = isActiveNav(href, pathname, hrefs);
        const label = navLabelFor(item, role);
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            title={isCollapsed ? label : undefined}
            className={
              active
                ? `flex ${isCollapsed ? "justify-center" : "items-center gap-2.5"} border-l-2 border-[#ec4899] bg-[#1f1f1f] px-3 py-2.5 text-sm font-medium text-white transition-all duration-150`
                : `flex ${isCollapsed ? "justify-center" : "items-center gap-2.5"} border-l-2 border-transparent px-3 py-2.5 text-sm text-[#a1a1aa] transition-all duration-150 hover:bg-[#1a1a1a] hover:text-[#d4d4d8] active:bg-[#1a1a1a]`
            }
          >
            <span className="relative shrink-0">
              <Icon size={16} strokeWidth={2} className="shrink-0" />
              {href === "/home" && blinkHome && (
                <span className="absolute -right-1.5 -top-1.5 flex h-3.5 w-3.5 animate-pulse items-center justify-center rounded-full bg-red-500 text-[9px] font-bold leading-none text-white">
                  !
                </span>
              )}
            </span>
            {!isCollapsed && <span className="min-w-0 flex-1">{label}</span>}
            {!isCollapsed && badge && (
              <span className="shrink-0 rounded-full bg-[#3f3f46] px-1.5 py-0.5 text-[10px] font-medium text-[#d4d4d8]">
                {badge}
              </span>
            )}
          </Link>
        );
      })}
    </nav>
  );
}
