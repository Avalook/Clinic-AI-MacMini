"use client";

// KHUNG ỨNG DỤNG — bản "Đề xuất" Tuyền chốt 27/09/2026 tối (trang mẫu khung.html):
//
//   * Nền xám nhạt; nội dung là MỘT TẤM TRẮNG bo góc nổi nhẹ (máy tính) — bỏ
//     đường kẻ cứng giữa thanh bên, thanh trên và nội dung.
//   * Thanh bên CÁCH 3: mặc định là thanh icon 60px; rê chuột (dừng 150ms) thì
//     bung ĐÈ lên nội dung — không đẩy trang; rời 250ms thì thu. 📌 Ghim = luôn
//     mở và chiếm chỗ như cũ; nhớ trên máy người dùng. Phím `[` ghim / bỏ ghim.
//   * Đầu thanh bên: dấu logo + tên phòng khám + cơ sở; đáy: người dùng + Thoát.
//   * Điện thoại: ngăn kéo trượt từ "Menu" của thanh dưới như trước.

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { X, LogOut, Pin, PinOff } from "lucide-react";
import Nav from "./Nav";
import BottomNav from "./BottomNav";
import { ROLE_LABEL, type ClinicRole } from "../../lib/roles";
import { type PhongTheoViTri } from "./nav-items";
import GlobalHeader from "./GlobalHeader";
import { QuyenProvider } from "./QuyenContext";

interface ShellProps {
  role: ClinicRole;
  identity: string;
  /** Tên người đang đăng nhập cho thẻ tên ở đầu trang. Không truyền thì đoán
   *  từ `identity` như trước (đoán sai khi `identity` có cơ sở ở cuối). */
  tenNguoi?: string;
  featureMode?: string;
  /** Mã vị trí người này đứng hôm nay (GET /me/vi-tri-hom-nay). */
  viTriHomNay?: readonly string[];
  /** Phòng của từng vị trí hôm nay (theo `room_id`). */
  phong?: PhongTheoViTri;
  /** Capability đang có — thanh bên bày thêm màn mà quyền mở được. */
  quyen?: readonly string[] | null;
  leaveAction: () => void | Promise<void>;
  children: React.ReactNode;
}

const KHOA_GHIM = "clinicai.sidebar.ghim";
const TRE_MO = 150;
const TRE_DONG = 250;

/** Dấu logo (chữ thập) — thay ảnh chữ "ClinicAI" 174×49 cũ, vừa thanh icon. */
function DauLogo() {
  return (
    <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-brand-600 text-white">
      <svg viewBox="0 0 24 24" width={16} height={16} fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinejoin="round" aria-hidden>
        <path d="M9 4h6v5h5v6h-5v5H9v-5H4V9h5z" />
      </svg>
    </span>
  );
}

function viet(s: string) {
  return s
    .trim()
    .split(/\s+/)
    .slice(-2)
    .map((w) => w[0]?.toLocaleUpperCase("vi-VN") ?? "")
    .join("");
}

export default function Shell({
  role,
  identity,
  tenNguoi,
  featureMode = "FULL_CLINIC",
  viTriHomNay = [],
  phong = {},
  quyen = null,
  leaveAction,
  children,
}: ShellProps) {
  // Drawer is opened from the bottom bar's "Menu"; each link / action closes it.
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const drawerRef = useRef<HTMLElement>(null);
  const drawerCloseRef = useRef<HTMLButtonElement>(null);
  const menuTriggerRef = useRef<HTMLElement | null>(null);

  // `identity` = "Vai (hôm nay) · Tên · Phòng khám · Cơ sở" — lấy 2 phần cuối.
  const phan = identity.split(" · ");
  const tenPhongKham = phan.length >= 4 ? phan[phan.length - 2] : "Dr4Women";
  const coSo = phan.length >= 3 ? phan[phan.length - 1] : "";
  const tenToi = tenNguoi?.trim() || (phan.length >= 2 ? phan[1] : identity);

  // ── Thanh bên máy tính: ghim + rê chuột bung ─────────────────────────────
  const [ghim, setGhim] = useState(false);
  const [bung, setBung] = useState(false);
  const hen = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    try {
      // Đọc sau khi gắn: máy chủ và trình duyệt vẽ giống nhau lúc đầu.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setGhim(localStorage.getItem(KHOA_GHIM) === "1");
    } catch {
      /* không đọc được thì mặc định thanh icon */
    }
  }, []);
  const doiGhim = () =>
    setGhim((g) => {
      try {
        localStorage.setItem(KHOA_GHIM, g ? "0" : "1");
      } catch {
        /* chỉ không nhớ */
      }
      setBung(false);
      return !g;
    });
  // Phím `[` ghim / bỏ ghim — trừ khi đang gõ trong ô nhập.
  useEffect(() => {
    const phim = (e: KeyboardEvent) => {
      if (e.key !== "[" || e.metaKey || e.ctrlKey || e.altKey) return;
      const t = e.target as HTMLElement | null;
      if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
      doiGhim();
    };
    window.addEventListener("keydown", phim);
    return () => window.removeEventListener("keydown", phim);
  }, []);
  const vao = () => {
    if (ghim) return;
    if (hen.current) clearTimeout(hen.current);
    hen.current = setTimeout(() => setBung(true), TRE_MO);
  };
  const ra = () => {
    if (hen.current) clearTimeout(hen.current);
    hen.current = setTimeout(() => setBung(false), TRE_DONG);
  };
  // Chuyển trang thì thu lại (bấm một mục xong không để thanh bung đè nội dung).
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setBung(false);
  }, [pathname]);
  const mo = ghim || bung;

  // Lock body scroll + move focus into the drawer while it's open.
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
        {/* Đầu: dấu logo + phòng khám / cơ sở + 📌 (máy tính) hoặc ✕ (điện thoại). */}
        <div className="mb-2 flex h-11 shrink-0 items-center gap-2.5 px-1.5">
          <DauLogo />
          {!collapsed && (
            <span className="min-w-0 flex-1 leading-tight">
              <span className="block truncate text-body font-semibold text-ink">{tenPhongKham}</span>
              {coSo ? <span className="block truncate text-label text-ink-muted">{coSo}</span> : null}
            </span>
          )}
          {!collapsed && !isMobile && (
            <button
              type="button"
              onClick={doiGhim}
              aria-pressed={ghim}
              title={ghim ? "Bỏ ghim — thu về thanh icon ( [ )" : "Ghim thanh bên luôn mở ( [ )"}
              aria-label={ghim ? "Bỏ ghim thanh bên" : "Ghim thanh bên"}
              className={`grid size-7 shrink-0 place-items-center rounded-control transition-colors hover:bg-surface-sunken ${
                ghim ? "text-brand-600" : "text-ink-faint hover:text-ink"
              }`}
            >
              {ghim ? <PinOff size={15} /> : <Pin size={15} />}
            </button>
          )}
          {isMobile && (
            <button
              ref={drawerCloseRef}
              type="button"
              onClick={closeDrawer}
              aria-label="Đóng menu"
              className="-mr-1 inline-flex size-9 items-center justify-center rounded-md text-ink-muted hover:bg-surface-sunken hover:text-ink md:hidden"
            >
              <X size={20} />
            </button>
          )}
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden">
          <Nav
            role={role}
            onNavigate={isMobile ? closeDrawer : undefined}
            isCollapsed={collapsed}
            featureMode={featureMode}
            viTriHomNay={viTriHomNay}
            phong={phong}
            quyen={quyen}
          />
        </div>
        {/* Đáy: người dùng + Thoát. LỐI PHỤ — lối chính là ảnh đại diện ở góc
            phải thanh trên (27/09/2026, đợt 3 — "log out cho lên trên bên phải"). */}
        <div className="mt-2 flex shrink-0 items-center gap-2.5 rounded-control px-1.5 py-1.5">
          <span className="grid size-7 shrink-0 place-items-center rounded-full bg-brand-100 text-label font-bold text-brand-700">
            {viet(tenToi) || "NV"}
          </span>
          {!collapsed && (
            <span className="min-w-0 flex-1 leading-tight">
              <span className="block truncate text-meta font-semibold text-ink">{tenToi}</span>
              <span className="block truncate text-label text-ink-muted">{ROLE_LABEL[role]}</span>
            </span>
          )}
          {!collapsed && (
            <form action={leaveAction}>
              <button
                type="submit"
                title="Thoát hệ thống"
                aria-label="Thoát hệ thống"
                className="grid size-7 place-items-center rounded-control text-ink-faint transition-colors hover:bg-surface-sunken hover:text-ink"
              >
                <LogOut size={15} />
              </button>
            </form>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="flex min-h-screen bg-surface-sunken font-sans">
      {/* Máy tính (≥md): ô giữ chỗ (60px, hoặc 248px khi ghim) + thanh bên nổi. */}
      <div
        className="relative hidden shrink-0 md:block"
        style={{ width: ghim ? 248 : 60 }}
      >
        <aside
          onMouseEnter={vao}
          onMouseLeave={ra}
          onFocus={vao}
          onBlur={(e) => {
            if (!e.currentTarget.contains(e.relatedTarget as Node | null)) ra();
          }}
          aria-label="Thanh bên"
          className={`fixed left-0 top-0 z-40 flex h-screen flex-col px-2 py-2.5 transition-[width,box-shadow] duration-200 ease-out motion-reduce:transition-none ${
            bung && !ghim ? "bg-surface shadow-panel" : "bg-surface-sunken"
          }`}
          style={{ width: mo ? 248 : 60 }}
        >
          {renderSidebar(!mo, false)}
        </aside>
      </div>

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
        className={`fixed inset-y-0 left-0 z-50 flex w-72 max-w-[80vw] flex-col bg-surface px-3 py-4 shadow-2xl transition-transform duration-300 ease-out motion-reduce:transition-none md:hidden ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {renderSidebar(false, true)}
      </aside>

      {/* TẤM NỘI DUNG — trắng, bo góc, nổi nhẹ trên nền xám (máy tính).
          `overflow-clip` (không phải hidden) để thanh trên vẫn dính khi cuộn. */}
      <div className="flex min-w-0 flex-1 flex-col bg-surface md:my-2 md:mr-2 md:overflow-clip md:rounded-2xl md:shadow-card md:ring-1 md:ring-line/60">
        <GlobalHeader
          identity={identity}
          tenNguoi={tenNguoi}
          role={role}
          quyen={quyen}
          featureMode={featureMode}
          leaveAction={leaveAction}
        />
        <main className="min-w-0 flex-1 p-4 pb-24 md:px-6 md:pb-8 md:pt-4">
          {/* key={pathname} PHẢI Ở ĐÂY. Bỏ nó đi thì React coi cây con của hai
              trang khác nhau là "cùng một chỗ" khi hình dạng trùng nhau, nên nó
              TÁI DÙNG instance component thay vì dựng mới: state chưa kiểm soát
              (ô nhập đang gõ dở, vị trí cuộn, dòng đang chọn) đi theo sang trang
              sau. Trên màn lâm sàng, một ô còn nội dung của bệnh nhân trước là
              lỗi không được phép có. Nó cũng là thứ khiến animation `page-in`
              chạy lại mỗi lần chuyển trang thay vì chỉ một lần khi mount. */}
          <div key={pathname} className="page-in">
            {/* Quyền cho component client (nút Check-out…) — cùng danh sách
                thanh bên đang dùng, không gọi mạng thêm. */}
            <QuyenProvider value={quyen}>{children}</QuyenProvider>
          </div>
        </main>
      </div>

      {/* Mobile bottom tab bar (<md). `featureMode` PHẢI truyền xuống: thiếu nó
          thì thanh dưới lọc khác thanh bên và điện thoại hiện lối vào những màn
          mà máy tính đã giấu. */}
      <BottomNav
        role={role}
        onMenu={openDrawer}
        featureMode={featureMode}
        viTriHomNay={viTriHomNay}
        phong={phong}
        quyen={quyen}
      />
    </div>
  );
}
