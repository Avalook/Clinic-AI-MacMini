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
import {
  isActiveNav,
  mucHienRa,
  mucThanhDuoi,
  navLabelFor,
  type PhongTheoViTri,
} from "./nav-items";

// How many destinations to surface as tabs before the rest collapse into Menu.
const MAX_TABS = 4;

export default function BottomNav({
  role,
  onMenu,
  featureMode = "FULL_CLINIC",
  viTriHomNay = [],
  phong = {},
  quyen = null,
}: {
  role: ClinicRole | null;
  onMenu: () => void;
  featureMode?: string;
  viTriHomNay?: readonly string[];
  phong?: PhongTheoViTri;
  /** Cùng luật với thanh bên — hai thanh lệch nhau là người dùng mất màn. */
  quyen?: readonly string[] | null;
}) {
  const pathname = usePathname();
  // CÙNG MỘT PHÉP LỌC VỚI THANH BÊN, kể cả `featureMode`.
  //
  // Bản trước gọi thẳng `NAV.filter(hienTrenThanhBen)` và bỏ qua featureMode,
  // nên khi phòng khám chạy chế độ CSKH_ONLY thì máy tính giấu các màn lâm sàng
  // còn điện thoại vẫn hiện lối vào. Hai thanh phải nói cùng một chuyện.
  const visible = mucHienRa(
    role,
    (r, href) => hienTrenThanhBen(r, href, quyen),
    featureMode,
    CLINICAL_HREFS,
    viTriHomNay,
    phong,
    // Ngày có ca, thanh bên dựng theo vị trí — vẫn phải lọc theo lego.
    quyen,
  );
  const allHrefs = visible.map((v) => v.href);
  // Có ca hôm nay thì `visible` ĐÃ xếp theo việc của hôm nay — lấy đầu danh sách
  // là đúng. Bảng `THANH_DUOI` theo vai chỉ dành cho ngày không có ca.
  const tabs =
    viTriHomNay.length > 0 && role !== "MANAGEMENT"
      ? visible.slice(0, MAX_TABS)
      : mucThanhDuoi(role, visible, MAX_TABS);

  const tabClass = (active: boolean) =>
    [
      // min-w-0: nút flex mặc định không co dưới TỪ dài nhất — "(khách của tôi)"
      // của bác sĩ đẩy nút Menu ra ngoài màn 375 (bấm thật 23/09).
      "flex min-w-0 flex-1 flex-col items-center justify-center gap-0.5 py-2 text-label font-medium transition-colors duration-150",
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
          // prefetch tắt — cùng lý do với thanh bên (Nav.tsx).
          <Link key={href} href={href} prefetch={false} className={tabClass(active)}>
            <Icon size={20} strokeWidth={active ? 2.4 : 2} />
            {/* CÙNG MỘT TÊN VỚI THANH BÊN. Chữ dài thì xuống dòng — hai dòng
                  10px vẫn đọc được, còn một cái tên bịa ngắn hơn thì không:
                  người dùng học "Danh sách bệnh nhân" trên máy tính rồi tìm
                  mãi không thấy nó trên điện thoại vì ở đó nó tên "BN đã khám".
                  Không cắt cụt bằng "…" — "Quản lý khá…" còn tệ hơn xuống dòng. */}
              <span className="max-w-full break-words px-0.5 text-center leading-tight">
                {navLabelFor(item, role)}
              </span>
          </Link>
        );
      })}
      <button
        type="button"
        onClick={onMenu}
        aria-label="Mở menu đầy đủ"
        className="flex min-w-0 flex-1 flex-col items-center justify-center gap-0.5 py-2 text-label font-medium text-ink-muted transition-colors duration-150 active:text-ink"
      >
        <Menu size={20} strokeWidth={2} />
        <span className="leading-none">Menu</span>
      </button>
    </nav>
  );
}
