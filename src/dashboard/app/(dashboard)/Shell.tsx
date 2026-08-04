"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { X, LogOut } from "lucide-react";
import Nav from "./Nav";
import BottomNav from "./BottomNav";
import { type ClinicRole } from "../../lib/roles";

interface ShellProps {
  role: ClinicRole;
  identity: string;
  featureMode?: string;
  leaveAction: () => void | Promise<void>;
  children: React.ReactNode;
}

import GlobalHeader from "./GlobalHeader";

export default function Shell({
  role,
  identity,
  featureMode = "FULL_CLINIC",
  leaveAction,
  children,
}: ShellProps) {
  // Drawer is opened from the bottom bar's "Menu"; each link / action closes it.
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const drawerRef = useRef<HTMLElement>(null);
  const drawerCloseRef = useRef<HTMLButtonElement>(null);
  const menuTriggerRef = useRef<HTMLElement | null>(null);

  // Desktop sidebar resizing and collapse state
  const [sidebarWidth, setSidebarWidth] = useState(248);
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
    drawerCloseRef.current?.focus();
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  function openDrawer() {
    menuTriggerRef.current = document.activeElement as HTMLElement | null;
    setOpen(true);
  }

  function closeDrawer() {
    setOpen(false);
    requestAnimationFrame(() => menuTriggerRef.current?.focus());
  }

  function handleDrawerKeyDown(event: React.KeyboardEvent<HTMLElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      closeDrawer();
      return;
    }
    if (event.key !== "Tab") return;

    const focusable = drawerRef.current?.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    if (!focusable?.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  const renderSidebar = (collapsed: boolean, isMobile = false) => {
    return (
      <div className="flex h-full flex-col">
        <div className="flex-1 min-h-0 space-y-6 overflow-y-auto">
          <div className={`flex items-center ${collapsed ? "justify-center" : "justify-between"} px-3`}>
            <h1 className="flex items-center text-base font-medium text-ink">
              <Image
                src="/clinicai-logo.svg"
                alt="ClinicAI"
                width={collapsed ? 42 : 174}
                height={collapsed ? 34 : 49}
                priority
                className="object-contain object-left"
              />
            </h1>
            {!collapsed && isMobile && (
              <button
                ref={drawerCloseRef}
                type="button"
                onClick={closeDrawer}
                aria-label="Đóng menu"
                className="-mr-1 inline-flex h-9 w-9 items-center justify-center rounded-md text-ink-muted hover:bg-surface-sunken hover:text-ink md:hidden"
              >
                <X size={20} />
              </button>
            )}
          </div>
          <Nav
            role={role}
            onNavigate={isMobile ? closeDrawer : undefined}
            isCollapsed={collapsed}
            featureMode={featureMode}
          />
        </div>

        <div className="shrink-0 space-y-2 border-t border-line/70 px-2 pt-3 pb-2">
          <form action={leaveAction}>
            <button
              type="submit"
              className={`w-full rounded-xl border border-line bg-surface-muted py-2 text-xs font-medium text-ink-muted transition-all hover:bg-surface-sunken hover:text-ink flex items-center justify-center shadow-xs ${collapsed ? "px-1.5" : "px-3 gap-2"}`}
              title={collapsed ? "Thoát hệ thống" : undefined}
            >
              <LogOut size={15} className="shrink-0 text-ink-muted" />
              {!collapsed && <span>Thoát</span>}
            </button>
          </form>
        </div>
      </div>
    );
  };

  return (
    <div className={`flex min-h-screen bg-surface-muted font-sans ${isResizing ? "select-none" : ""}`}>
      {/* Desktop sidebar (≥md). */}
      <aside
        className="hidden flex-col bg-surface px-3 py-4 md:flex shrink-0 min-h-screen sticky top-0 h-screen relative select-none border-r border-line"
        style={{ width: isCollapsed ? 68 : sidebarWidth }}
      >
        {renderSidebar(isCollapsed, false)}

        {/* Resize handle */}
        <div
          onMouseDown={startResizing}
          className="absolute right-0 top-0 bottom-0 w-1.5 cursor-col-resize hover:bg-brand-700/50 active:bg-brand-600 transition-colors"
          style={{ zIndex: 50 }}
        />
      </aside>

      {/* Mobile drawer (<md) */}
      <div
        onClick={closeDrawer}
        aria-hidden
        className={`fixed inset-0 z-40 bg-black/40 transition-opacity duration-300 motion-reduce:transition-none md:hidden ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      />
      <aside
        ref={drawerRef}
        role="dialog"
        aria-modal="true"
        aria-label="Menu điều hướng"
        aria-hidden={!open}
        inert={!open}
        onKeyDown={handleDrawerKeyDown}
        className={`fixed inset-y-0 left-0 z-50 flex w-72 max-w-[80vw] flex-col bg-surface px-3 py-5 shadow-2xl transition-transform duration-300 ease-out motion-reduce:transition-none md:hidden ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {renderSidebar(false, true)}
      </aside>

      {/* Main Column with Global Header */}
      <div className="min-w-0 flex-1 flex flex-col">
        <GlobalHeader
          onToggleSidebar={() => setIsCollapsed(!isCollapsed)}
          isCollapsed={isCollapsed}
          identity={identity}
          role={role}
        />
        <main className="min-w-0 flex-1 p-4 pb-24 md:p-6 md:pb-8">
          {/* key={pathname} PHẢI Ở ĐÂY. Bỏ nó đi thì React coi cây con của hai
              trang khác nhau là "cùng một chỗ" khi hình dạng trùng nhau, nên nó
              TÁI DÙNG instance component thay vì dựng mới: state chưa kiểm soát
              (ô nhập đang gõ dở, vị trí cuộn, dòng đang chọn) đi theo sang trang
              sau. Trên màn lâm sàng, một ô còn nội dung của bệnh nhân trước là
              lỗi không được phép có. Nó cũng là thứ khiến animation `page-in`
              chạy lại mỗi lần chuyển trang thay vì chỉ một lần khi mount. */}
          <div key={pathname} className="page-in">
            {children}
          </div>
        </main>
      </div>

      {/* Mobile bottom tab bar (<md). */}
      <BottomNav role={role} onMenu={openDrawer} />
    </div>
  );
}
