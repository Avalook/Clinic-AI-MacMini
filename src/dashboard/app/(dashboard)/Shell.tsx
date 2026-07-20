"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { X, LogOut, ChevronLeft, ChevronRight } from "lucide-react";
import Nav from "./Nav";
import BottomNav from "./BottomNav";
import { type ClinicRole } from "../../lib/roles";

interface ShellProps {
  role: ClinicRole;
  identity: string;
  leaveAction: () => void | Promise<void>;
  children: React.ReactNode;
}

export default function Shell({
  role,
  identity,
  leaveAction,
  children,
}: ShellProps) {
  // Drawer is opened from the bottom bar's "Menu"; each link / action closes it.
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  // Desktop sidebar resizing and collapse state
  const [sidebarWidth, setSidebarWidth] = useState(220);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isResizing, setIsResizing] = useState(false);

  const startResizing = (mouseDownEvent: React.MouseEvent) => {
    mouseDownEvent.preventDefault();
    setIsResizing(true);
  };

  useEffect(() => {
    if (!isResizing) return;

    const doResize = (mouseMoveEvent: MouseEvent) => {
      const newWidth = mouseMoveEvent.clientX;
      if (newWidth < 90) {
        setIsCollapsed(true);
      } else {
        setIsCollapsed(false);
        if (newWidth >= 160 && newWidth <= 450) {
          setSidebarWidth(newWidth);
        } else if (newWidth < 160) {
          setSidebarWidth(160);
        } else if (newWidth > 450) {
          setSidebarWidth(450);
        }
      }
    };

    const stopResizing = () => {
      setIsResizing(false);
    };

    window.addEventListener("mousemove", doResize);
    window.addEventListener("mouseup", stopResizing);
    return () => {
      window.removeEventListener("mousemove", doResize);
      window.removeEventListener("mouseup", stopResizing);
    };
  }, [isResizing]);

  // Prevent body scroll when the drawer is open.
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  const renderSidebar = (collapsed: boolean, isMobile = false) => {
    return (
      <div className="flex h-full flex-col">
        {/* Vùng Nav CUỘN (min-h-0 + overflow) → nhiều mục (vd Quản lý) không đẩy
            footer 'Thoát' + nút thu/mở ra ngoài màn hình. Footer ghim đáy. */}
        <div className="flex-1 min-h-0 space-y-6 overflow-y-auto">
          <div className={`flex items-center ${collapsed ? "justify-center" : "justify-between"} px-3`}>
            <h1 className="flex items-center gap-2 text-base font-medium text-white">
              <Image
                src="/logo.png"
                alt="Dr4Women"
                width={24}
                height={24}
                className="rounded-full object-contain"
              />
              {!collapsed && "Dr4Women"}
            </h1>
            {!collapsed && isMobile && (
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Đóng menu"
                className="-mr-1 inline-flex h-9 w-9 items-center justify-center rounded-md text-[#a1a1aa] hover:bg-[#1a1a1a] hover:text-white md:hidden"
              >
                <X size={20} />
              </button>
            )}
          </div>
          <Nav role={role} onNavigate={() => setOpen(false)} isCollapsed={collapsed} />
        </div>

        <div className="shrink-0 space-y-3 border-t border-[#1f1f1f] px-3 pt-4">
          {!collapsed && (
            <p className="truncate text-xs text-[#71717a]" title={identity}>
              {identity}
            </p>
          )}
          <form action={leaveAction}>
            <button
              type="submit"
              className={`w-full rounded-md border border-[#262626] py-2 text-sm text-[#a1a1aa] transition-colors duration-150 hover:bg-[#1a1a1a] hover:text-[#d4d4d8] active:bg-[#1a1a1a] flex items-center justify-center ${collapsed ? "px-1" : "px-3 gap-2"}`}
              title={collapsed ? "Thoát" : undefined}
            >
              <LogOut size={14} className="shrink-0" />
              {!collapsed && <span>Thoát</span>}
            </button>
          </form>

          {/* Toggle collapse/expand button (only shown on desktop sidebar) */}
          {!isMobile && (
            <button
              type="button"
              onClick={() => setIsCollapsed(!collapsed)}
              className="hidden md:flex h-8 w-full items-center justify-center rounded-md border border-[#1f1f1f] text-[#a1a1aa] hover:bg-[#1a1a1a] hover:text-white transition-colors"
              title={collapsed ? "Mở rộng sidebar" : "Thu gọn sidebar"}
            >
              {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
            </button>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className={`flex min-h-screen bg-[#fafafa] font-sans ${isResizing ? "select-none" : ""}`}>
      {/* Mobile top bar (brand only). Hidden on ≥md. */}
      <header className="fixed inset-x-0 top-0 z-20 flex h-12 items-center justify-center border-b border-[#1f1f1f] bg-[#0a0a0a] px-3 md:hidden">
        <span className="flex items-center gap-2 text-sm font-medium text-white">
          <Image
            src="/logo.png"
            alt="Dr4Women"
            width={24}
            height={24}
            className="rounded-full object-contain"
          />
          Dr4Women
        </span>
      </header>

      {/* Desktop sidebar (≥md). */}
      <aside
        className="hidden flex-col bg-[#0a0a0a] px-3 py-5 md:flex shrink-0 min-h-screen sticky top-0 h-screen relative select-none"
        style={{ width: isCollapsed ? 64 : sidebarWidth }}
      >
        {renderSidebar(isCollapsed, false)}

        {/* Resize handle */}
        <div
          onMouseDown={startResizing}
          className="absolute right-0 top-0 bottom-0 w-1.5 cursor-col-resize hover:bg-[#ec4899]/50 active:bg-[#ec4899] transition-colors"
          style={{ zIndex: 50 }}
        />
      </aside>

      {/* Mobile drawer (<md), opened from the bottom bar's Menu. */}
      <div
        onClick={() => setOpen(false)}
        aria-hidden
        className={`fixed inset-0 z-40 bg-black/40 transition-opacity duration-300 motion-reduce:transition-none md:hidden ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      />
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-72 max-w-[80vw] flex-col bg-[#0a0a0a] px-3 py-5 shadow-2xl transition-transform duration-300 ease-out motion-reduce:transition-none md:hidden ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {renderSidebar(false, true)}
      </aside>

      {/* Content. Padding leaves room for the mobile top bar + bottom nav. */}
      <main className="min-w-0 flex-1 p-4 pb-24 pt-16 md:p-8 md:pb-8 md:pt-8">
        {/* key=pathname → fade chạy lại mỗi lần đổi trang */}
        <div key={pathname} className="page-in">
          {children}
        </div>
      </main>

      {/* Mobile bottom tab bar (<md). */}
      <BottomNav role={role} onMenu={() => setOpen(true)} />
    </div>
  );
}
