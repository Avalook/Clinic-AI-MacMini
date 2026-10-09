"use client";

import { useEffect, useRef, useState } from "react";
import { VN_TZ, vnToday } from "../../lib/datetime";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Bell,
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  AlertCircle,
  LogOut,
  MapPin,
} from "lucide-react";
import Button from "@/components/ui/Button";
import NutHoanTac from "@/components/ui/NutHoanTac";
import { lenhHoanTac } from "./_lam-viec/hoan-tac";
import { ROLE_LABEL, type ClinicRole } from "@/lib/roles";
import { NAV, navLabelFor } from "./nav-items";
import { NHOM_CONG_VIEC } from "./nav-items";
import TimNhanh from "./TimNhanh";
import { useNotifications } from "./NotificationContext";

interface GlobalHeaderProps {
  identity: string;
  /** Tên người đang đăng nhập (layout truyền). Thiếu thì đoán từ `identity`. */
  tenNguoi?: string;
  role: ClinicRole;
  /** Quyền + chế độ — cho ô tìm nhanh ⌘K lọc đúng như thanh bên. */
  quyen?: readonly string[] | null;
  featureMode?: string;
  /** Server action thoát — cùng action với nút Thoát ở chân thanh bên. */
  leaveAction: () => void | Promise<void>;
  /** Tên cơ sở đang đứng (máy chủ trả theo cơ sở đã chọn). */
  coSo?: string;
}

export default function GlobalHeader({
  identity,
  tenNguoi,
  role,
  quyen = null,
  featureMode = "FULL_CLINIC",
  leaveAction,
  coSo,
}: GlobalHeaderProps) {
  const pathname = usePathname();
  const headerRef = useRef<HTMLElement>(null);
  // Đã cuộn trang chưa — thanh trên chỉ hiện đường kẻ dưới khi nội dung trôi qua.
  const [daCuon, setDaCuon] = useState(false);
  useEffect(() => {
    const doi = () => setDaCuon(window.scrollY > 4);
    doi();
    window.addEventListener("scroll", doi, { passive: true });
    return () => window.removeEventListener("scroll", doi);
  }, []);
  const theTenRef = useRef<HTMLDivElement>(null);
  const nutTenRef = useRef<HTMLButtonElement>(null);

  // TÊN NGƯỜI ĐĂNG NHẬP. `identity` là "Vai · Tên · Phòng khám · Cơ sở", nên
  // lấy phần CUỐI (cách cũ) ra tên cơ sở chứ không phải tên người — thẻ tên
  // từng ghi "Cơ sở …" với chữ tắt của cơ sở. Layout truyền thẳng tên; chỉ
  // khi thiếu mới đoán như cũ.
  const staffName = tenNguoi?.trim() || (identity.split(" · ").at(-1) ?? identity);
  const staffInitials = staffName
    .trim()
    .split(/\s+/)
    .slice(-2)
    .map((w) => w[0]?.toLocaleUpperCase("vi-VN") ?? "")
    .join("") || "NV";

  // Dynamic Live Clock (Vietnam Time)
  const [liveTime, setLiveTime] = useState("");
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setLiveTime(
        now.toLocaleTimeString("vi-VN", {
          hour: "2-digit",
          minute: "2-digit",
          hour12: false,
          timeZone: VN_TZ,
        }),
      );
    };
    updateTime();
    const timer = setInterval(updateTime, 10000);
    return () => clearInterval(timer);
  }, []);

  // Popover States (Mutually Exclusive)
  const [calOpen, setCalOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  // Thẻ tên → ô nhỏ có nút Thoát (27/09/2026, đợt 3).
  const [theTenOpen, setTheTenOpen] = useState(false);

  // Click Outside Listener
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      const t = e.target as Node;
      if (headerRef.current && !headerRef.current.contains(t)) {
        setCalOpen(false);
        setNotifOpen(false);
      }
      // Thẻ tên đóng cả khi bấm chỗ khác TRONG đầu trang (chuông, lịch…).
      if (theTenRef.current && !theTenRef.current.contains(t)) {
        setTheTenOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const toggleCal = () => {
    const mo = !calOpen;
    setCalOpen(mo);
    if (mo) {
      setNotifOpen(false);
      setTheTenOpen(false);
    }
  };

  const toggleNotif = () => {
    const mo = !notifOpen;
    setNotifOpen(mo);
    if (mo) {
      setCalOpen(false);
      setTheTenOpen(false);
    }
  };

  const toggleTheTen = () => {
    const mo = !theTenOpen;
    setTheTenOpen(mo);
    if (mo) {
      setCalOpen(false);
      setNotifOpen(false);
    }
  };

  /** Esc đóng và trả tiêu điểm về thẻ tên (bàn phím không bị lạc). */
  const phimTheTen = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Escape" && theTenOpen) {
      e.preventDefault();
      setTheTenOpen(false);
      nutTenRef.current?.focus();
    }
  };

  /** Tab ra khỏi thẻ tên thì đóng. `relatedTarget` rỗng (bấm chuột vào chữ
   *  trong ô, Safari không đặt tiêu điểm lên nút) KHÔNG đóng — nếu đóng ở đây
   *  thì cú bấm "Thoát" mất trước khi tới nút; bấm ra ngoài đã có mousedown lo. */
  const roiTheTen = (e: React.FocusEvent<HTMLDivElement>) => {
    const toi = e.relatedTarget as Node | null;
    if (toi && !e.currentTarget.contains(toi)) setTheTenOpen(false);
  };

  // Mini Calendar Popover State.
  //
  // Mặc định là HÔM NAY. Trước đây ba dòng này ghim `new Date(2026, 4, 14)` —
  // ngày viết component — nên mọi màn hình đều đội một cái ngày sai ở đầu
  // trang, bất kể hôm nay là ngày nào.
  //
  // `vnToday()` hỏi thẳng lịch Asia/Ho_Chi_Minh chứ không đọc giờ máy, nên máy
  // chủ (chạy UTC) và trình duyệt (+07) ra cùng một ngày — không lệch hydrate.
  // Dùng `new Date()` trần ở đây thì từ 00:00 tới 07:00 giờ VN hai bên ra hai
  // ngày khác nhau.
  const [selectedDate, setSelectedDate] = useState(() => vnToday());
  const [viewYear, setViewYear] = useState(() => vnToday().getFullYear());
  const [viewMonth, setViewMonth] = useState(() => vnToday().getMonth());

  const dateStr = selectedDate.toLocaleDateString("vi-VN", {
    weekday: "long",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: VN_TZ,
  });
  const formattedDateStr = dateStr.charAt(0).toUpperCase() + dateStr.slice(1);
  // Bản gọn cho màn hẹp — cùng một ngày, chỉ khác cách viết.
  const shortDateStr = selectedDate.toLocaleDateString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: VN_TZ,
  });

  // CHUÔNG ĐỌC NGUỒN THẬT (NotificationContext), KHÔNG CÒN BA DÒNG VIẾT CỨNG.
  //
  // Trước đây chỗ này là một mảng gõ tay, trong đó có một dòng ĐỎ
  // "Cảnh báo quá SLA 15 phút ca KH-260514-012" — một mã ca không tồn tại — và
  // nó hiện trên MỌI trang, cho MỌI vai, mọi ngày. Nghĩa là mỗi nhân viên mở
  // app đều thấy chuông đỏ số 3 và không lần nào trong đó là thật.
  //
  // Cái giá không phải là ba dòng sai. Là cả phòng khám học được rằng chuông đỏ
  // không có nghĩa gì — nên đến lúc có cảnh báo thật thì không ai nhìn nữa.
  //
  // Nguồn thật hiện có: quyết định duyệt/từ chối ca làm việc của CHÍNH mình
  // (NotificationContext, realtime + poll). Ít hơn ba dòng kia rất nhiều, và
  // chuông im khi không có gì — đó mới là điều làm nó đáng tin.
  const { notifs, unread: unreadCount, markAllRead, danhDauDaXuLy, docLai } =
    useNotifications();

  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
  const firstDayOfWeek = new Date(viewYear, viewMonth, 1).getDay();

  const monthNames = [
    "Tháng 1", "Tháng 2", "Tháng 3", "Tháng 4", "Tháng 5", "Tháng 6",
    "Tháng 7", "Tháng 8", "Tháng 9", "Tháng 10", "Tháng 11", "Tháng 12",
  ];

  const prevMonth = () => {
    if (viewMonth === 0) {
      setViewMonth(11);
      setViewYear((y) => y - 1);
    } else {
      setViewMonth((m) => m - 1);
    }
  };

  const nextMonth = () => {
    if (viewMonth === 11) {
      setViewMonth(0);
      setViewYear((y) => y + 1);
    } else {
      setViewMonth((m) => m + 1);
    }
  };

  const getPageTitle = () => {
    if (pathname.startsWith("/customers")) {
      return { title: "Quản lý khách hàng", subtitle: "Theo dõi trạng thái và bước tiếp theo của từng khách hàng" };
    }
    if (pathname.startsWith("/settings/tai-khoan")) {
      return {
        title: "Thiết lập tài khoản cho nhân viên",
        subtitle: "Tạo login, đặt lại mật khẩu, gỡ tài khoản.",
      };
    }
    if (pathname.startsWith("/nhan-su")) {
      return {
        title: "Quản lý nhân sự",
        subtitle:
          "Hồ sơ từng người: vai trò, cơ sở làm việc, loại hợp đồng, giấy phép hành nghề.",
      };
    }
    if (pathname.startsWith("/patients/new")) {
      return {
        // MỘT câu đúng cho cả hai luồng (CSKH đặt lịch trước · Lễ tân tiếp
        // khách vãng lai) — thanh này không đọc được `?mode=`, và hai nút chọn
        // luồng ngay dưới đã nói rõ người dùng đang ở đâu.
        title: "Tạo hồ sơ bệnh nhân",
        subtitle:
          "Nhập thông tin hành chính, xác minh và đưa khách vào đúng luồng tiếp nhận.",
      };
    }
    if (pathname.startsWith("/patient-list")) {
      return {
        title: "Danh sách bệnh nhân",
        subtitle: "Tra cứu hồ sơ hành chính và lượt hẹn gần nhất của người bệnh.",
      };
    }
    if (pathname.startsWith("/nhac-tai-kham")) {
      return {
        title: "Nhắc tái khám",
        // Phụ đề cũ chỉ mô tả lượt 1 ("chưa đặt lịch lại"). Từ 07/08 màn này
        // có HAI lượt, và lượt 2 đúng là những người ĐÃ đặt lịch — để nguyên
        // câu cũ thì nó nói ngược với nửa dưới của chính màn hình.
        subtitle:
          "Hai lượt gọi: mời đặt lịch trước hẹn 7 ngày, và nhắc đi khám vào sáng ngày hẹn.",
      };
    }
    // ĐÚNG /appointments — trang con "Chờ xếp bác sĩ" lấy tên nút của nó từ
    // NAV bên dưới (18/09/2026: startsWith làm nó hiện "Đặt lịch hẹn").
    if (pathname === "/appointments") {
      return { title: "Đặt lịch hẹn", subtitle: "Chọn khung giờ còn sức chứa và xác nhận lịch cho khách hàng" };
    }
    if (pathname.startsWith("/audit-log")) {
      return { title: "Lịch sử thao tác", subtitle: "Tra cứu ai đã thực hiện thay đổi, vào thời điểm nào và dữ liệu nào bị ảnh hưởng" };
    }
    if (pathname.startsWith("/do-sinh-hieu")) {
      return { title: "Đo sinh hiệu" };
    }
    if (pathname.startsWith("/reception/checkout")) {
      return {
        title: "Check-out lượt khám",
        subtitle:
          "Đối soát điều kiện rồi đóng lượt. Còn việc chưa xong vẫn đóng được, nhưng phải ghi lý do.",
      };
    }
    if (pathname.startsWith("/reception")) {
      return { title: "Tiếp đón khách", subtitle: "Check-in khách hẹn hôm nay và xếp hàng chờ" };
    }
    // KHÔNG CÓ TIÊU ĐỀ RIÊNG ⇒ LẤY ĐÚNG TÊN NÚT Ở THANH BÊN (18/09/2026).
    //
    // Rà ngày 18/09: 32/46 mục thanh bên — Bàn khám, các phòng dịch vụ, Thu
    // tiền, Điều phối ca, Kho thuốc… — rơi xuống câu chung "Hệ thống Quản lý
    // ClinicAI". Viết thêm 32 nhánh thì lần thêm màn sau lại quên; lấy từ NAV
    // (nguồn duy nhất của tên nút) thì tên trên thanh bên và tiêu đề trang
    // không thể lệch nhau. Khớp đường dài nhất: /truong-ca/tv thắng /truong-ca.
    const muc = NAV.filter(
      (n) => pathname === n.href || pathname.startsWith(`${n.href}/`),
    ).sort((x, y) => y.href.length - x.href.length)[0];
    if (muc) return { title: navLabelFor(muc, role), subtitle: "" };
    return { title: "Hệ thống Quản lý ClinicAI", subtitle: "Quy trình phòng khám liên thông thông minh" };
  };

  const { title, subtitle } = getPageTitle();

  // Nhóm công việc của trang — phần đầu đường dẫn "Nhóm › Trang".
  const nhomCuaTrang =
    NHOM_CONG_VIEC.find((g) =>
      g.hrefs.some((h) => h !== "/home" && (pathname === h || pathname.startsWith(`${h}/`))),
    )?.ten ?? null;
  // "CN 27/09" — gọn, cùng ngày đang chọn ở lịch nhỏ.
  const ngayGon = `${
    ["CN", "T2", "T3", "T4", "T5", "T6", "T7"][
      new Date(selectedDate.toLocaleDateString("en-US", { timeZone: VN_TZ })).getDay()
    ]
  } ${shortDateStr.slice(0, 5)}`;

  return (
    // THANH TRÊN (bản "Đề xuất", Tuyền chốt 27/09/2026 tối): 48px, trong tấm
    // nội dung, không viền quanh từng món; đường kẻ dưới chỉ hiện khi đã cuộn.
    <header
      ref={headerRef}
      className={`sticky top-0 z-30 flex h-12 w-full items-center justify-between gap-3 bg-surface/85 px-4 backdrop-blur-md transition-[border-color] md:px-6 border-b ${
        daCuon ? "border-line" : "border-transparent"
      }`}
    >
      {/* Trái: ĐƯỜNG DẪN "Nhóm › Trang" thay tiêu đề to (trang đã có tiêu đề riêng). */}
      <div className="flex min-w-0 items-center gap-1.5 text-meta" title={subtitle || undefined}>
        {nhomCuaTrang ? (
          <>
            <span className="hidden truncate text-ink-muted sm:inline">{nhomCuaTrang}</span>
            <ChevronRight size={13} className="hidden shrink-0 text-ink-faint sm:block" aria-hidden />
          </>
        ) : null}
        <h1 className="truncate font-semibold text-ink">{title}</h1>
      </div>

      {/* Right Section: Widgets */}
      <div className="flex shrink-0 items-center gap-1 sm:gap-2">
        <TimNhanh role={role} quyen={quyen} featureMode={featureMode} />
        {/* Ngày · giờ — MỘT dòng chữ nhạt (bấm vẫn mở lịch nhỏ). */}
        <div className="relative">
          <button
            type="button"
            onClick={toggleCal}
            title={formattedDateStr}
            className="h-8 rounded-control px-2 text-meta tabular-nums text-ink-muted transition-colors hover:bg-surface-sunken hover:text-ink"
          >
            <span className="hidden md:inline">{ngayGon} · {liveTime || "--:--"}</span>
            <span className="md:hidden">{shortDateStr}</span>
          </button>

          {/* Mini Calendar Popover */}
          {calOpen && (
            <div className="absolute right-0 top-10 z-50 w-72 rounded-2xl border border-line bg-surface p-4 shadow-panel animate-in fade-in slide-in-from-top-2 duration-150">
              <div className="mb-3 flex items-center justify-between">
                <span className="text-sm font-bold text-ink">
                  {monthNames[viewMonth]} {viewYear}
                </span>
                <div className="flex items-center gap-1">
                  <button
                    onClick={prevMonth}
                    className="grid size-7 place-items-center rounded-lg text-ink-muted hover:bg-surface-muted"
                  >
                    <ChevronLeft size={16} />
                  </button>
                  <button
                    onClick={nextMonth}
                    className="grid size-7 place-items-center rounded-lg text-ink-muted hover:bg-surface-muted"
                  >
                    <ChevronRight size={16} />
                  </button>
                </div>
              </div>

              {/* Day Labels */}
              <div className="mb-2 grid grid-cols-7 text-center text-label font-semibold text-ink-muted">
                <span>CN</span>
                <span>T2</span>
                <span>T3</span>
                <span>T4</span>
                <span>T5</span>
                <span>T6</span>
                <span>T7</span>
              </div>

              {/* Calendar Grid */}
              <div className="grid grid-cols-7 gap-1 text-center text-xs">
                {Array.from({ length: firstDayOfWeek }).map((_, i) => (
                  <div key={`empty-${i}`} />
                ))}
                {Array.from({ length: daysInMonth }).map((_, i) => {
                  const dayNum = i + 1;
                  const isSelected =
                    selectedDate.getDate() === dayNum &&
                    selectedDate.getMonth() === viewMonth &&
                    selectedDate.getFullYear() === viewYear;
                  return (
                    <button
                      key={dayNum}
                      onClick={() => {
                        setSelectedDate(new Date(viewYear, viewMonth, dayNum));
                        setCalOpen(false);
                      }}
                      className={`grid size-8 place-items-center rounded-full font-medium transition-colors ${
                        isSelected
                          ? "bg-brand-600 text-white font-bold"
                          : "text-ink hover:bg-brand-50"
                      }`}
                    >
                      {dayNum}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Notification Bell Widget */}
        <div className="relative">
          <button
            type="button"
            onClick={toggleNotif}
            aria-label="Thông báo"
            className="relative grid size-8 place-items-center rounded-control text-ink-muted transition-colors hover:bg-surface-sunken hover:text-ink"
          >
            <Bell size={16} />
            {unreadCount > 0 && (
              <span className="absolute right-0.5 top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-danger px-1 text-label font-bold leading-none text-white ring-2 ring-surface">
                {unreadCount}
              </span>
            )}
          </button>

          {/* Notifications Popover */}
          {notifOpen && (
            <div className="absolute right-0 top-10 z-50 w-80 rounded-2xl border border-line bg-surface p-4 shadow-panel space-y-3 animate-in fade-in slide-in-from-top-2 duration-150">
              <div className="flex items-center justify-between border-b border-line pb-2">
                <span className="text-xs font-bold text-ink">Thông báo mới</span>
                {unreadCount > 0 && (
                  <button
                    onClick={markAllRead}
                    className="text-label font-medium text-brand-600 hover:underline"
                  >
                    Đánh dấu đã đọc
                  </button>
                )}
              </div>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {notifs.length === 0 ? (
                  <p className="px-1 py-3 text-center text-xs text-ink-muted">
                    Chưa có thông báo nào.
                  </p>
                ) : (
                  notifs.map((n) => {
                    // BẤM VÀO LÀ SANG THẲNG TRANG XỬ LÝ.
                    //
                    // Thông báo đã mang sẵn `duong_dan` từ lúc backend sinh ra
                    // nó ("Cần xếp bác sĩ" → /appointments/cho-xep-bac-si),
                    // nhưng giao diện chỉ in chữ ra rồi thôi. Người đọc biết có
                    // việc mà phải tự đi tìm màn nào xử lý — với quản lý đang có
                    // hai mươi mục trên thanh bên thì đó là một bước thừa mỗi
                    // lần chuông kêu.
                    const noiDung = (
                      <>
                      {n.khan ? (
                        // Thông báo KHẨN do Trưởng ca gọi — đây là cái đỏ THẬT,
                        // thay cho ba dòng viết cứng đã gỡ hôm nay.
                        <AlertCircle
                          size={15}
                          className="mt-0.5 shrink-0 text-danger"
                        />
                      ) : n.approved ? (
                        <CheckCircle2
                          size={15}
                          className="mt-0.5 shrink-0 text-success"
                        />
                      ) : (
                        <AlertCircle
                          size={15}
                          className="mt-0.5 shrink-0 text-warning"
                        />
                      )}
                      <div className="min-w-0 flex-1">
                        <p className="font-medium leading-tight text-ink">
                          {n.title}
                        </p>
                        <p className="text-label text-ink-soft">{n.detail}</p>
                        <span className="text-label text-ink-muted">{n.at}</span>
                        {n.duongDan && (
                          <span className="mt-0.5 block text-label font-semibold text-brand-700">
                            Bấm để xử lý →
                          </span>
                        )}
                      </div>
                      </>
                    );
                    const lop = `flex w-full items-start gap-2.5 rounded-xl p-2.5 text-left text-xs ${
                      n.khan ? "bg-danger-bg" : "bg-brand-50/70"
                    }`;
                    // NÚT ĐÓNG VIỆC, TÁCH KHỎI Ô BẤM ĐỂ ĐI.
                    //
                    // `cua_toi()` lọc `da_xu_ly_luc IS NULL`, và cho tới
                    // 10/08/2026 KHÔNG một màn nào gọi endpoint đóng việc — nên
                    // mọi thông báo từng sinh ra nằm lại trong chuông mãi mãi,
                    // và người dùng học cách bỏ qua cả cái chuông.
                    //
                    // Không đóng hộ khi bấm vào đường dẫn: đi xem một việc
                    // không phải là đã làm xong nó.
                    // "Chỉ định bị bỏ" (Khối 2, Tuyền 06/10/2026): nút DUY
                    // NHẤT là Hoàn tác — không có "Xong"/"Đã biết". Hoàn tác
                    // xong máy chủ tự đóng thông báo.
                    const nutXong = n.chiHoanTac ? (
                      n.hoanTacSoId ? (
                        <NutHoanTac
                          className="shrink-0 self-start"
                          goi={lenhHoanTac("hoan-tac-bo-chi-dinh", n.hoanTacSoId)}
                          onXong={docLai}
                          moTa="Đặt lại chỉ định vừa bị bỏ"
                        />
                      ) : null
                    ) : n.thongBaoId ? (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          void danhDauDaXuLy(n.thongBaoId!);
                        }}
                        title="Đã làm xong việc này — bỏ khỏi chuông"
                        className="shrink-0 self-start rounded-lg border border-line bg-surface px-1.5 py-0.5 text-label font-semibold text-ink-soft hover:bg-surface-muted"
                      >
                        Xong
                      </button>
                    ) : null;
                    return n.duongDan ? (
                      <div key={n.key} className={`${lop} items-center`}>
                        <Link
                          href={n.duongDan}
                          onClick={() => setNotifOpen(false)}
                          className="flex min-w-0 flex-1 items-start gap-2.5 transition-colors hover:brightness-95"
                        >
                          {noiDung}
                        </Link>
                        {nutXong}
                      </div>
                    ) : (
                      <div key={n.key} className={lop}>
                        {noiDung}
                        {nutXong}
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          )}
        </div>

        {/* CƠ SỞ ĐANG ĐỨNG (08/10/2026 — hai cơ sở). Luôn hiện để không ai làm
            nhầm cơ sở mà không biết; bấm để đổi. Phòng khám một cơ sở thì
            /chon-co-so tự quay lại ngay. */}
        {coSo ? (
          <Link
            href={`/chon-co-so?doi=1&next=${encodeURIComponent(pathname || "/home")}`}
            // Không tải trước: đường dẫn mang `pathname` nên đổi ở MỌI trang —
            // staging 09/10 tải trước nó 138 lần trong 24 phút.
            prefetch={false}
            title="Đổi cơ sở"
            className="flex min-h-8 max-w-40 items-center gap-1 rounded-full border border-line px-2.5 text-meta font-medium text-ink-soft transition-colors hover:border-brand-600 hover:text-brand-700"
          >
            <MapPin size={14} className="shrink-0 text-brand-600" aria-hidden />
            <span className="truncate">{coSo}</span>
          </Link>
        ) : null}

        {/* THẺ TÊN — BẤM ĐƯỢC, MỞ Ô CÓ NÚT THOÁT (27/09/2026, đợt 3).
            Góp ý phòng khám: "log out 'chữ Thoát' cho lên trên bên phải". Trước
            đây Thoát chỉ ở chân thanh bên; điện thoại phải mở Menu rồi cuộn.
            Nút ở thanh bên vẫn giữ làm lối phụ. Cùng server action. */}
        <div
          ref={theTenRef}
          className="relative"
          onKeyDown={phimTheTen}
          onBlur={roiTheTen}
        >
          <button
            ref={nutTenRef}
            type="button"
            onClick={toggleTheTen}
            aria-haspopup="true"
            aria-expanded={theTenOpen}
            aria-controls="the-ten-tai-khoan"
            aria-label={`Tài khoản ${staffName} — bấm để thoát`}
            title={`${staffName} · ${ROLE_LABEL[role]}`}
            className="grid size-8 place-items-center rounded-full transition-shadow hover:ring-2 hover:ring-brand-100"
          >
            {/* Chỉ ẢNH ĐẠI DIỆN — tên + vai nằm ở đáy thanh bên (bản Đề xuất). */}
            <span className="grid size-7 shrink-0 place-items-center rounded-full bg-brand-100 text-xs font-bold text-brand-700">
              {staffInitials}
            </span>
          </button>

          {theTenOpen && (
            <div
              id="the-ten-tai-khoan"
              role="group"
              aria-label="Tài khoản đang đăng nhập"
              className="absolute right-0 top-10 z-50 w-64 rounded-card border border-line bg-surface p-3 shadow-panel"
            >
              <p className="truncate text-emph font-semibold text-ink">{staffName}</p>
              <p className="text-meta text-ink-muted">{ROLE_LABEL[role]}</p>
              <p className="mt-0.5 text-meta text-ink-muted">{identity}</p>
              <form action={leaveAction} className="mt-3 border-t border-line pt-3">
                <Button type="submit" variant="secondary" size="lg" className="w-full">
                  <LogOut size={16} aria-hidden />
                  Thoát
                </Button>
              </form>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
