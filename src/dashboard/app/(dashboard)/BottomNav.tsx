"use client";

// Mobile bottom tab bar (thumb-reach navigation, like a native app). Shows the
// first few role-visible destinations + a "Menu" button that opens the full
// drawer (secondary items, role switch, logout). Hidden on ≥md, where the
// sidebar takes over. The active tab uses the shared brand teal token.

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu } from "lucide-react";
import { hienTrenThanhBen, type ClinicRole } from "../../lib/roles";
import { CLINICAL_HREFS } from "../../lib/feature-mode-client";
import { isActiveNav, mucHienRa, mucThanhDuoi, navLabelFor } from "./nav-items";

// How many destinations to surface as tabs before the rest collapse into Menu.
const MAX_TABS = 4;

export default function BottomNav({
  role,
  onMenu,
  featureMode = "FULL_CLINIC",
}: {
  role: ClinicRole | null;
  onMenu: () => void;
  featureMode?: string;
}) {
  const pathname = usePathname();
  // CÙNG MỘT PHÉP LỌC VỚI THANH BÊN, kể cả `featureMode`.
  //
  // Bản trước gọi thẳng `NAV.filter(hienTrenThanhBen)` và bỏ qua featureMode,
  // nên khi phòng khám chạy chế độ CSKH_ONLY thì máy tính giấu các màn lâm sàng
  // còn điện thoại vẫn hiện lối vào. Hai thanh phải nói cùng một chuyện.
  const visible = mucHienRa(role, hienTrenThanhBen, featureMode, CLINICAL_HREFS);
  const allHrefs = visible.map((v) => v.href);
  const tabs = mucThanhDuoi(role, visible, MAX_TABS);

  const tabClass = (active: boolean) =>
    [
      "flex flex-1 flex-col items-center justify-center gap-0.5 py-2 text-[10px] font-medium transition-colors duration-150",
      active ? "text-brand-600" : "text-ink-muted active:text-ink",
    ].join(" ");

  return (
    <nav
      aria-label="Điều hướng"
      className="fixed inset-x-0 bottom-0 z-30 flex border-t border-line bg-white pb-[env(safe-area-inset-bottom)] shadow-panel md:hidden"
    >
      {tabs.map((item) => {
        const { href, icon: Icon } = item;
        const active = isActiveNav(href, pathname, allHrefs);
        return (
          <Link key={href} href={href} className={tabClass(active)}>
            <Icon size={20} strokeWidth={active ? 2.4 : 2} />
            {/* CÙNG MỘT TÊN VỚI THANH BÊN. Chữ dài thì xuống dòng — hai dòng
                  10px vẫn đọc được, còn một cái tên bịa ngắn hơn thì không:
                  người dùng học "Danh sách bệnh nhân" trên máy tính rồi tìm
                  mãi không thấy nó trên điện thoại vì ở đó nó tên "BN đã khám".
                  Không cắt cụt bằng "…" — "Quản lý khá…" còn tệ hơn xuống dòng. */}
              <span className="px-0.5 text-center leading-tight">
                {navLabelFor(item, role)}
              </span>
          </Link>
        );
      })}
      <button
        type="button"
        onClick={onMenu}
        aria-label="Mở menu đầy đủ"
        className="flex flex-1 flex-col items-center justify-center gap-0.5 py-2 text-[10px] font-medium text-ink-muted transition-colors duration-150 active:text-ink"
      >
        <Menu size={20} strokeWidth={2} />
        <span className="leading-none">Menu</span>
      </button>
    </nav>
  );
}
