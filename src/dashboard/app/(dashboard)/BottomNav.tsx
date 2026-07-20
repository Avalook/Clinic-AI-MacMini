"use client";

// Mobile bottom tab bar (thumb-reach navigation, like a native app). Shows the
// first few role-visible destinations + a "Menu" button that opens the full
// drawer (secondary items, role switch, logout). Hidden on ≥md, where the
// sidebar takes over. The active tab is highlighted in the brand rose.

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu } from "lucide-react";
import { canSeeNav, type ClinicRole } from "../../lib/roles";
import { NAV, isActiveNav, navLabelFor } from "./nav-items";

// How many destinations to surface as tabs before the rest collapse into Menu.
const MAX_TABS = 4;

export default function BottomNav({
  role,
  onMenu,
}: {
  role: ClinicRole | null;
  onMenu: () => void;
}) {
  const pathname = usePathname();
  const visible = NAV.filter((item) => canSeeNav(role, item.href));
  const allHrefs = visible.map((v) => v.href);
  const tabs = visible.slice(0, MAX_TABS);

  const tabClass = (active: boolean) =>
    [
      "flex flex-1 flex-col items-center justify-center gap-0.5 py-2 text-[10px] font-medium transition-colors duration-150",
      active ? "text-[#ec4899]" : "text-[#71717a] active:text-[#171717]",
    ].join(" ");

  return (
    <nav
      aria-label="Điều hướng"
      className="fixed inset-x-0 bottom-0 z-30 flex border-t border-[#e4e4e7] bg-white pb-[env(safe-area-inset-bottom)] shadow-[0_-1px_3px_rgba(0,0,0,0.06)] md:hidden"
    >
      {tabs.map((item) => {
        const { href, icon: Icon } = item;
        const active = isActiveNav(href, pathname, allHrefs);
        return (
          <Link key={href} href={href} className={tabClass(active)}>
            <Icon size={20} strokeWidth={active ? 2.4 : 2} />
            <span className="leading-none">{navLabelFor(item, role, true)}</span>
          </Link>
        );
      })}
      <button
        type="button"
        onClick={onMenu}
        aria-label="Mở menu đầy đủ"
        className="flex flex-1 flex-col items-center justify-center gap-0.5 py-2 text-[10px] font-medium text-[#71717a] transition-colors duration-150 active:text-[#171717]"
      >
        <Menu size={20} strokeWidth={2} />
        <span className="leading-none">Menu</span>
      </button>
    </nav>
  );
}
