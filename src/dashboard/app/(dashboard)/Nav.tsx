"use client";

// Desktop sidebar nav links + the drawer's link list. Visibility is per-role
// (see canSeeNav). Client component so it can highlight the active route.
//
// Light surface, teal active state, per the design set. The old dark rail used
// a gender-coded accent; the icon system explicitly forbids that treatment,
// and the shared teal token keeps the shell neutral.

import { useTransition } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { canSeeNav, ROLE_LABEL, type ClinicRole } from "../../lib/roles";
import { NAV, isActiveNav, navLabelFor } from "./nav-items";
import { useNotifications } from "./NotificationContext";
import { CLINICAL_HREFS } from "../../lib/feature-mode-client";

export default function Nav({
  role,
  onNavigate,
  isCollapsed = false,
  featureMode = "FULL_CLINIC",
}: {
  role: ClinicRole | null;
  /** Called after a nav item is tapped (used to close the mobile drawer). */
  onNavigate?: () => void;
  isCollapsed?: boolean;
  featureMode?: string;
}) {
  const pathname = usePathname();
  // Đang ở trang KHÁC mà có thông báo lịch chưa xem → nhấp nháy "!" ở mục Trang chủ
  // (chuông chỉ nằm ở Trang chủ; đây là tín hiệu nhắc người dùng quay về xem).
  const { unread } = useNotifications();
  const blinkHome = unread > 0 && pathname !== "/home";
  const visible = NAV.filter((item) => {
    if (!canSeeNav(role, item.href)) return false;
    // CSKH_ONLY mode: ẩn các màn hình lâm sàng khỏi sidebar.
    if (featureMode === "CSKH_ONLY" && CLINICAL_HREFS.has(item.href)) return false;
    return true;
  });
  const hrefs = visible.map((v) => v.href);

  // PHẢN HỒI TỨC THÌ KHI BẤM, KHÔNG PHẢI TỰ VẼ TRẠNG THÁI ĐANG-ĐẾN.
  //
  // Bản trước giữ một `pendingHref` rồi tô sáng mục đó thay cho mục thật sự
  // đang mở, và xoá nó trong useEffect([pathname]). Hai chỗ hỏng:
  //
  //   * usePathname() BỎ QUA query string, nên đi từ /appointments sang
  //     /appointments?scope=me không đổi pathname → effect không chạy →
  //     pendingHref kẹt lại.
  //   * trong lúc pendingHref còn set, `isRealActive && !pendingHref` làm mục
  //     ĐANG mở mất tô sáng. Người dùng thấy sidebar chỉ vào một trang chưa tới
  //     trong khi nội dung vẫn là trang cũ.
  //
  // useTransition là cơ chế sẵn có của React cho đúng việc này: `isPending` chỉ
  // đúng trong lúc điều hướng còn chạy và tự tắt khi xong HOẶC khi bị huỷ. Mục
  // đang mở giữ nguyên tô sáng; mục đang tới hiện một thanh tiến trình mảnh.
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  return (
    <nav className="space-y-0.5">
      {!isCollapsed && role ? (
        <p className="px-3 pb-2 text-xs font-semibold uppercase tracking-wider text-ink-muted">
          {ROLE_LABEL[role]}
        </p>
      ) : null}
      {visible.map((item) => {
        const { href, badge, icon: Icon } = item;
        const active = isActiveNav(href, pathname, hrefs);
        const label = navLabelFor(item, role);
        return (
          <Link
            key={href}
            href={href}
            // prefetch KHÔNG bật cứng. Với App Router, prefetch={true} kéo về
            // TOÀN BỘ payload RSC kể cả route force-dynamic — tức chạy trọn bộ
            // truy vấn server của trang đó. Sidebar có ~30 mục và Next prefetch
            // mọi link lọt vào khung nhìn, nên chỉ mở sidebar đã có thể châm
            // ngòi cho ba mươi lượt render server. Mặc định (auto) dừng ở ranh
            // giới loading.tsx — vốn đã có ở (dashboard)/loading.tsx — nên vẫn
            // vào trang tức thì mà không kéo theo cái giá đó.
            onClick={(e) => {
              if (onNavigate) onNavigate();
              // Điều hướng trong một transition để isPending phản ánh đúng lúc
              // trang đích còn đang tải, thay vì đoán bằng state thủ công.
              if (
                e.metaKey || e.ctrlKey || e.shiftKey || e.altKey ||
                e.button !== 0
              ) {
                return; // mở tab mới: để trình duyệt lo
              }
              e.preventDefault();
              startTransition(() => router.push(href));
            }}
            title={isCollapsed ? label : undefined}
            className={
              active
                ? `flex ${isCollapsed ? "justify-center" : "items-center gap-2.5"} rounded-control border-l-[3px] border-brand-600 bg-brand-50 px-3 py-2.5 text-sm font-medium text-brand-700 transition-colors`
                : `flex ${isCollapsed ? "justify-center" : "items-center gap-2.5"} rounded-control border-l-[3px] border-transparent px-3 py-2.5 text-sm text-ink-soft transition-colors hover:bg-surface-sunken hover:text-ink active:bg-surface-sunken`
            }
          >
            <span className="relative shrink-0">
              <Icon size={16} strokeWidth={2} className="shrink-0" />
              {href === "/home" && blinkHome && (
                <span className="absolute -right-1.5 -top-1.5 flex h-3.5 w-3.5 animate-pulse items-center justify-center rounded-full bg-red-500 text-[9px] font-bold leading-none text-white motion-reduce:animate-none">
                  !
                </span>
              )}
            </span>
            {!isCollapsed && (
              <span className="min-w-0 flex-1 truncate">{label}</span>
            )}
            {!isCollapsed && isPending && active && (
              <span
                aria-hidden
                className="h-1 w-1 shrink-0 animate-pulse rounded-full bg-brand-600 motion-reduce:animate-none"
              />
            )}
            {!isCollapsed && badge && (
              <span className="shrink-0 rounded-full bg-surface-sunken px-1.5 py-0.5 text-[10px] font-medium text-ink-muted">
                {badge}
              </span>
            )}
          </Link>
        );
      })}
      {/* CSKH_ONLY mode indicator */}
      {featureMode === "CSKH_ONLY" && !isCollapsed && (
        <div className="mx-3 mt-3 rounded-md border border-brand-200 bg-brand-50 px-2.5 py-1.5 text-[11px] font-medium text-brand-700">
          ⚡ Chế độ CSKH
        </div>
      )}
    </nav>
  );
}

