"use client";

// Desktop sidebar nav links + the drawer's link list. Visibility is per-role
// (see canSeeNav). Client component so it can highlight the active route.
//
// Light surface, teal active state, per the design set. The old dark rail used
// a gender-coded accent; the icon system explicitly forbids that treatment,
// and the shared teal token keeps the shell neutral.

import { useEffect, useState, useTransition } from "react";
import { ChevronDown as ChevronDownData, ChevronRight as ChevronRightData } from "lucide";
import { MorphIcon } from "morphicons/react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { hienTrenThanhBen, type ClinicRole } from "../../lib/roles";
import {
  isActiveNav,
  navLabelFor,
  nhomTheoCongViec,
  nhomThanhBen,
  xepNodeCon,
  type NavItem,
  type PhongTheoViTri,
} from "./nav-items";
import { useNotifications } from "./NotificationContext";
import { BIEN_HINH } from "./nav-bien-hinh";

// Nhóm đã gập — nhớ trên máy người dùng (tiện ích, không phải dữ liệu).
const KHOA_GAP = "clinicai.nav.nhom-gap";
function docGap(): string[] {
  try {
    const luu = localStorage.getItem(KHOA_GAP);
    if (luu === null) return ["viec-khac"]; // chưa chỉnh lần nào: "Việc khác" gập
    const v = JSON.parse(luu);
    return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : [];
  } catch {
    return [];
  }
}
import { CLINICAL_HREFS } from "../../lib/feature-mode-client";

export default function Nav({
  role,
  onNavigate,
  isCollapsed = false,
  featureMode = "FULL_CLINIC",
  viTriHomNay = [],
  phong = {},
  quyen = null,
}: {
  role: ClinicRole | null;
  /** Phòng của từng vị trí hôm nay — mục phòng mang tên phòng thật. */
  phong?: PhongTheoViTri;
  /** Mã vị trí hôm nay — thanh bên đi theo việc thật (xem `mucHienRa`). */
  viTriHomNay?: readonly string[];
  /** Capability đang có. Màn nào quyền mở được thì bày, dù vai không có. */
  quyen?: readonly string[] | null;
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
  // Cùng hàm với thanh dưới (BottomNav) — xem `mucHienRa`. Trước đây mỗi bên
  // tự lọc và hai bên đã lệch nhau ở chế độ CSKH_ONLY.
  // Nhóm theo VAI hôm nay + "Việc khác" — `nhomThanhBen` lọc qua `mucHienRa`.
  const tho = nhomThanhBen(
    role,
    (r, href) => hienTrenThanhBen(r, href, quyen),
    featureMode,
    CLINICAL_HREFS,
    viTriHomNay,
    phong,
    // Ngày có ca, thanh bên dựng theo vị trí — vẫn phải lọc theo lego.
    quyen,
  );
  // Node con (Nhắc tái khám) đứng ngay dưới node cha (Quản lý khách hàng).
  // Lego ĐANG BẬT của chính tài khoản (7a, 27/09) là nhóm RIÊNG, MỞ sẵn — gộp
  // vào "Việc khác" (gập sẵn) là giấu đúng việc người ấy được bật để làm. Từ
  // 28/09 gập được như mọi nhóm, tiêu đề chỉ còn mũi tên.
  const { dau: dau0, nhom: nhom0, lego: lego0, khac: khac0 } = tho;
  const [dau, lego, khac, ...mucNhom] = xepNodeCon([
    dau0,
    lego0,
    khac0,
    ...nhom0.map((g) => g.muc),
  ]);
  const nhom = nhom0.map((g, i) => ({ ...g, muc: mucNhom[i] }));
  const laCon = (item: NavItem) =>
    Boolean(item.cha) &&
    [...dau, ...lego, ...khac, ...mucNhom.flat()].some((m) => m.href === item.cha);
  const visible = [...dau, ...nhom.flatMap((g) => g.muc), ...lego, ...khac];
  const hrefs = visible.map((v) => v.href);
  const coHaiPhan = nhom.length > 0;
  // "Việc khác" GẬP SẴN (ngày có lịch) — xem `docGap`; đang đứng ở một màn trong
  // đó thì `veNhom` vẫn mở, không giấu chỗ người dùng đang ở.

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
  // Mục đang rê chuột / đang có tiêu điểm — icon của nó biến hình (nav-bien-hinh).
  const [re, setRe] = useState<string | null>(null);
  // Nhóm công việc đang gập (kiểu A, 27/09/2026).
  const [gap, setGap] = useState<string[]>(["viec-khac"]);
  useEffect(() => {
    // Đọc sau khi gắn để máy chủ và trình duyệt vẽ giống nhau lúc đầu.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setGap(docGap());
  }, []);
  // Các nhóm của thanh bên, theo đúng thứ tự vẽ. Nhóm lego KHÔNG CÓ CHỮ (Tuyền
  // 28/09: "bỏ chữ lego đi, chỉ là mũi tên toggle thôi").
  const cacNhom: { ma: string; ten: string; muc: NavItem[] }[] = coHaiPhan
    ? [
        ...nhom.map((g) => ({ ma: `vt-${g.nhom}`, ten: g.ten, muc: g.muc })),
        ...(lego.length > 0 ? [{ ma: "lego-dang-bat", ten: "", muc: lego }] : []),
        ...(khac.length > 0
          ? [{ ma: "viec-khac", ten: `Việc khác (${khac.length})`, muc: khac }]
          : []),
      ]
    : nhomTheoCongViec([...dau, ...lego, ...khac]);
  const nhomDangO =
    cacNhom.find((g) => g.muc.some((m) => isActiveNav(m.href, pathname, hrefs)))?.ma ??
    null;
  // Tới một trang nằm trong nhóm đang gập → mở nhóm ấy (một lần, không ép mãi).
  useEffect(() => {
    if (!nhomDangO) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setGap((g) => (g.includes(nhomDangO) ? g.filter((x) => x !== nhomDangO) : g));
  }, [nhomDangO]);
  const doiGap = (ma: string) =>
    setGap((g) => {
      const moi = g.includes(ma) ? g.filter((x) => x !== ma) : [...g, ma];
      try {
        localStorage.setItem(KHOA_GAP, JSON.stringify(moi));
      } catch {
        /* máy không cho lưu thì chỉ không nhớ */
      }
      return moi;
    });

  const veLink = (item: NavItem) => {
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
              // BẤM LẠI NÚT CỦA TRANG ĐANG MỞ = TẢI LẠI TRANG ẤY.
              //
              // Tuyền 14/08/2026: *"khi click vào lại nút nào của sidebar thì
              // tự load lại trang đó"*. `router.push` sang chính URL đang đứng
              // là lệnh rỗng — Next thấy không có gì để điều hướng nên không
              // làm gì, và người dùng bấm xong thấy y nguyên màn cũ. Ở màn CSKH
              // thì "y nguyên" nghĩa là danh sách khách vẫn là ảnh chụp lúc mở,
              // trong khi ca trực khác vừa ghi thêm việc.
              //
              // `refresh()` chạy lại server component của đúng route ấy và giữ
              // nguyên trạng thái đang gõ dở trong các ô — khác hẳn F5, thứ
              // quét sạch cả trang.
              startTransition(() =>
                pathname === href ? router.refresh() : router.push(href),
              );
            }}
            title={isCollapsed ? label : undefined}
            onMouseEnter={() => setRe(href)}
            onMouseLeave={() => setRe((r) => (r === href ? null : r))}
            onFocus={() => setRe(href)}
            onBlur={() => setRe((r) => (r === href ? null : r))}
            // KIỂU A (27/09/2026): dòng 36px (con 32px), mục đang mở = nền nhạt +
            // chữ brand, không còn vạch trái.
            className={`flex ${isCollapsed ? "h-9 justify-center" : `${laCon(item) ? "h-8 text-meta" : "h-9 text-sm"} items-center gap-2.5`} rounded-control px-2.5 transition-colors ${
              active
                ? "bg-brand-50 font-medium text-brand-700"
                : "text-ink-soft hover:bg-surface-sunken hover:text-ink active:bg-surface-sunken"
            }`}
          >
            <span className="relative shrink-0">
              {BIEN_HINH[href] ? (
                <MorphIcon
                  icon={re === href ? BIEN_HINH[href].re : BIEN_HINH[href].tinh}
                  spring={BIEN_HINH[href].lo}
                  reducedMotion="user"
                  size={16}
                  strokeWidth={2}
                  className="shrink-0"
                />
              ) : (
                <Icon size={16} strokeWidth={2} className="shrink-0" />
              )}
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
              <span className="shrink-0 rounded-full bg-surface-sunken px-1.5 py-0.5 text-label font-medium text-ink-muted">
                {badge}
              </span>
            )}
          </Link>
        );
      };

  // Node con đứng dưới node cha, thụt vào kèm ĐƯỜNG KẺ DỌC mảnh (kiểu A).
  const tatCa = [...dau, ...lego, ...khac, ...mucNhom.flat()];
  const veMuc = (item: NavItem) => {
    if (laCon(item)) return null;
    const con = tatCa.filter((m) => m.cha === item.href);
    if (con.length === 0) return veLink(item);
    if (isCollapsed) return [item, ...con].map(veLink);
    return (
      <div key={item.href}>
        {veLink(item)}
        <div className="ml-4.5 border-l border-line pl-1.5">{con.map(veLink)}</div>
      </div>
    );
  };

  // Tiêu đề nhóm: chữ hoa nhỏ màu nhạt, bấm để gập/mở, mũi tên BIẾN HÌNH.
  // MỌI nhóm gập / mở được (Tuyền 28/09/2026: "các mũi tên ở sidebar đang lỗi
  // không đóng mở được" — trước: nhóm vị trí + nhóm lego vẽ mũi tên mà không
  // gập, nhóm đang đứng bị ÉP mở). Nhóm chứa trang đang đứng tự MỞ một lần khi
  // tới trang (effect dưới), sau đó người dùng gập được.
  const veNhom = (g: { ma: string; ten: string; muc: NavItem[] }) => {
    const mo = isCollapsed || !gap.includes(g.ma);
    return (
      <div key={g.ma} className="pt-3 first:pt-0">
        {isCollapsed ? (
          <div className="mx-2 mb-1 border-t border-line" aria-hidden />
        ) : (
          <button
            type="button"
            onClick={() => doiGap(g.ma)}
            aria-expanded={mo}
            aria-label={g.ten ? undefined : `${mo ? "Gập" : "Mở"} nhóm việc đang được mở`}
            className="flex w-full items-center gap-1 rounded-control px-2.5 py-1 text-left text-label font-semibold uppercase tracking-wider text-ink-faint hover:text-ink-muted"
          >
            <MorphIcon
              icon={mo ? ChevronDownData : ChevronRightData}
              spring="snappy"
              reducedMotion="user"
              size={12}
              strokeWidth={2.5}
            />
            {g.ten ? <span className="truncate">{g.ten}</span> : null}
          </button>
        )}
        {mo ? <div className="space-y-0.5">{g.muc.map(veMuc)}</div> : null}
      </div>
    );
  };

  return (
    <nav className="space-y-0.5">
      {coHaiPhan ? (
        <>
          {dau.map(veMuc)}
          {/* MỖI VỊ TRÍ HÔM NAY MỘT NHÓM (Tuyền 16/09/2026) — giữ nguyên, chỉ
              đổi cách trình bày theo kiểu A; "Việc khác" là một nhóm gập được. */}
          {cacNhom.map(veNhom)}
        </>
      ) : (
        // KHÔNG có lịch hôm nay: chia theo công việc (nav-items `NHOM_CONG_VIEC`).
        cacNhom.map(veNhom)
      )}
      {/* CSKH_ONLY mode indicator */}
      {featureMode === "CSKH_ONLY" && !isCollapsed && (
        <div className="mx-3 mt-3 rounded-md border border-brand-200 bg-brand-50 px-2.5 py-1.5 text-label font-medium text-brand-700">
          ⚡ Chế độ CSKH
        </div>
      )}
    </nav>
  );
}

