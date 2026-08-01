"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { X, LogOut, ChevronLeft, ChevronRight } from "lucide-react";
import Nav from "./Nav";
import BottomNav from "./BottomNav";
import { ROLE_LABEL, type ClinicRole } from "../../lib/roles";

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
  const isClinicalWorkspace =
    pathname.startsWith("/reception/queue") ||
    pathname.startsWith("/doctor/board") ||
    pathname.startsWith("/doctor/orders/") ||
    pathname.startsWith("/cashier/board");
  const staffName = identity.split(" · ").at(-1) ?? identity;
  const staffInitials = staffName
    .trim()
    .split(/\s+/)
    .slice(-2)
    .map((word) => word[0]?.toLocaleUpperCase("vi-VN") ?? "")
    .join("");
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
        {/* Vùng Nav CUỘN (min-h-0 + overflow) → nhiều mục (vd Quản lý) không đẩy
            footer 'Thoát' + nút thu/mở ra ngoài màn hình. Footer ghim đáy. */}
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
          />
        </div>

        <div className="shrink-0 space-y-3 border-t border-line px-3 pt-4">
          {!collapsed && !isClinicalWorkspace && (
            <p className="truncate text-xs text-ink-muted" title={identity}>
              {identity}
            </p>
          )}
          <form action={leaveAction}>
            <button
              type="submit"
              className={`w-full rounded-md border border-line py-2 text-sm text-ink-muted transition-colors duration-150 hover:bg-surface-sunken hover:text-ink active:bg-surface-sunken flex items-center justify-center ${collapsed ? "px-1" : "px-3 gap-2"}`}
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
              className="hidden md:flex h-8 w-full items-center justify-center rounded-md border border-line text-ink-muted hover:bg-surface-sunken hover:text-ink transition-colors"
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
    <div className={`flex min-h-screen bg-surface-muted font-sans ${isResizing ? "select-none" : ""}`}>
      {/* Mobile top bar (brand only). Hidden on ≥md. */}
      <header className="fixed inset-x-0 top-0 z-20 flex h-12 items-center justify-center border-b border-line bg-surface px-3 md:hidden">
        <span className="flex items-center gap-2 text-sm font-medium text-ink">
          <Image
            src="/clinicai-logo.svg"
            alt="ClinicAI"
            width={92}
            height={30}
            priority
            className="object-contain"
          />
        </span>
      </header>

      {/* Desktop sidebar (≥md). */}
      <aside
        className="hidden flex-col bg-surface px-3 py-5 md:flex shrink-0 min-h-screen sticky top-0 h-screen relative select-none"
        style={{ width: isCollapsed ? 64 : sidebarWidth }}
      >
        {renderSidebar(isCollapsed, false)}

        {/* Resize handle */}
        <div
          onMouseDown={startResizing}
          className="absolute right-0 top-0 bottom-0 w-1.5 cursor-col-resize hover:bg-brand-700/50 active:bg-brand-600 transition-colors"
          style={{ zIndex: 50 }}
        />
      </aside>

      {/* Mobile drawer (<md), opened from the bottom bar's Menu. */}
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

      {/* Content. Padding leaves room for the mobile top bar + bottom nav. */}
      <main
        className={
          isClinicalWorkspace
            ? "relative min-w-0 flex-1 p-3 pb-24 pt-16 md:p-4 md:pb-4 md:pt-4"
            : "min-w-0 flex-1 p-4 pb-24 pt-16 md:p-8 md:pb-8 md:pt-8"
        }
      >
        {isClinicalWorkspace ? (
          <div className="absolute right-4 top-3 hidden items-center gap-2 border-l border-line pl-3 md:flex">
            <span className="flex h-9 w-9 items-center justify-center rounded-full border border-line bg-surface-sunken text-xs font-semibold text-ink-soft">
              {staffInitials || "NV"}
            </span>
            <span className="max-w-36">
              <span className="block truncate text-xs font-semibold text-ink">{staffName}</span>
              <span className="block text-[11px] text-ink-muted">{ROLE_LABEL[role]}</span>
            </span>
          </div>
        ) : null}
        {/* key=pathname → fade chạy lại mỗi lần đổi trang */}
        <div
          key={pathname}
          className={isClinicalWorkspace ? "page-in [&>main>header]:pr-44" : "page-in"}
        >
          {children}
        </div>
      </main>

      {/* Mobile bottom tab bar (<md). */}
      <BottomNav role={role} onMenu={openDrawer} />
    </div>
  );
}
