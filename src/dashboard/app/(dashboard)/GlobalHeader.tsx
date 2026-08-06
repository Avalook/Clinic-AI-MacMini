"use client";

import { useEffect, useRef, useState } from "react";
import { VN_TZ, vnToday } from "../../lib/datetime";
import Image from "next/image";
import { usePathname } from "next/navigation";
import {
  Menu,
  Calendar as CalendarIcon,
  Clock,
  Bell,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  CheckCircle2,
  AlertCircle,
  Info,
} from "lucide-react";
import { ROLE_LABEL, type ClinicRole } from "@/lib/roles";

interface GlobalHeaderProps {
  onToggleSidebar: () => void;
  isCollapsed: boolean;
  identity: string;
  role: ClinicRole;
}

export default function GlobalHeader({
  onToggleSidebar,
  isCollapsed,
  identity,
  role,
}: GlobalHeaderProps) {
  const pathname = usePathname();
  const headerRef = useRef<HTMLElement>(null);

  // Extract staff name and initials
  const staffName = identity.split(" · ").at(-1) ?? identity;
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

  // Click Outside Listener
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (headerRef.current && !headerRef.current.contains(e.target as Node)) {
        setCalOpen(false);
        setNotifOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const toggleCal = () => {
    setCalOpen((prev) => {
      if (!prev) setNotifOpen(false);
      return !prev;
    });
  };

  const toggleNotif = () => {
    setNotifOpen((prev) => {
      if (!prev) setCalOpen(false);
      return !prev;
    });
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

  // Dynamic Notifications State
  const [notifications, setNotifications] = useState([
    {
      id: "1",
      title: "Có 2 ca mới chờ CSKH xác nhận",
      time: "08:15",
      unread: true,
      type: "info",
    },
    {
      id: "2",
      title: "BS. Phan Chí Thành đã duyệt kết quả khám",
      time: "08:00",
      unread: true,
      type: "success",
    },
    {
      id: "3",
      title: "Cảnh báo quá SLA 15 phút ca KH-260514-012",
      time: "07:45",
      unread: true,
      type: "alert",
    },
  ]);

  const unreadCount = notifications.filter((n) => n.unread).length;

  const markAllRead = () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, unread: false })));
  };

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
    if (pathname.startsWith("/cskh-tasks")) {
      return { title: "Nhiệm vụ chăm sóc", subtitle: "Theo dõi, thực hiện và ghi nhận kết quả chăm sóc khách hàng" };
    }
    if (pathname.startsWith("/customers")) {
      return { title: "Quản lý khách hàng", subtitle: "Theo dõi trạng thái và bước tiếp theo của từng khách hàng" };
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
        subtitle:
          "Người được bác sĩ hẹn tái khám nhưng chưa đặt lịch lại. Ai đặt được lịch rồi thì tự rời danh sách này.",
      };
    }
    if (pathname.startsWith("/tasks")) {
      return { title: "Công việc chăm sóc", subtitle: "Theo dõi, thực hiện và ghi nhận kết quả chăm sóc khách hàng" };
    }
    if (pathname.startsWith("/appointments")) {
      return { title: "Đặt lịch hẹn", subtitle: "Chọn khung giờ còn sức chứa và xác nhận lịch cho khách hàng" };
    }
    if (pathname.startsWith("/audit-log")) {
      return { title: "Lịch sử thao tác", subtitle: "Tra cứu ai đã thực hiện thay đổi, vào thời điểm nào và dữ liệu nào bị ảnh hưởng" };
    }
    if (pathname.startsWith("/reception/checkout")) {
      return {
        title: "Check-out lượt khám",
        subtitle:
          "Đối soát điều kiện rồi đóng lượt. Còn việc chưa xong vẫn đóng được, nhưng phải ghi lý do.",
      };
    }
    if (pathname.startsWith("/reception")) {
      return { title: "Hàng đợi tiếp nhận", subtitle: "Tiếp đón và phân luồng bệnh nhân" };
    }
    if (pathname.startsWith("/doctor")) {
      return { title: "Bàn khám bác sĩ", subtitle: "Khám bệnh, kê đơn và chỉ định cận lâm sàng" };
    }
    if (pathname.startsWith("/cashier")) {
      return { title: "Bàn thu ngân", subtitle: "Thanh toán và xuất hóa đơn dịch vụ" };
    }
    return { title: "Hệ thống Quản lý ClinicAI", subtitle: "Quy trình phòng khám liên thông thông minh" };
  };

  const { title, subtitle } = getPageTitle();

  return (
    <header ref={headerRef} className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-line bg-surface/95 px-4 backdrop-blur-md">
      {/* Left Section: Hamburger + Logo/Title */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onToggleSidebar}
          aria-label={isCollapsed ? "Mở rộng sidebar" : "Thu gọn sidebar"}
          className="grid size-9 place-items-center rounded-xl border border-line bg-surface text-ink-muted transition-all hover:bg-surface-muted hover:text-ink shadow-xs"
        >
          <Menu size={18} />
        </button>

        {isCollapsed && (
          <Image
            src="/clinicai-logo.svg"
            alt="ClinicAI"
            width={120}
            height={36}
            priority
            className="object-contain hidden md:block"
          />
        )}

        <div className="hidden sm:block">
          <h1 className="text-base font-bold text-ink leading-tight">{title}</h1>
          <p className="text-[11px] text-ink-muted leading-none">{subtitle}</p>
        </div>
      </div>

      {/* Right Section: Widgets */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Date Dropdown Widget */}
        <div className="relative">
          <button
            type="button"
            onClick={toggleCal}
            className="flex items-center gap-1.5 rounded-xl border border-line bg-surface px-3 py-1.5 text-xs font-medium text-ink shadow-xs hover:bg-surface-muted transition-all"
          >
            <CalendarIcon size={14} className="text-brand-600 shrink-0" />
            <span className="hidden md:inline">{formattedDateStr}</span>
            <span className="md:hidden">{shortDateStr}</span>
            <ChevronDown size={13} className="text-ink-muted" />
          </button>

          {/* Mini Calendar Popover */}
          {calOpen && (
            <div className="absolute right-0 top-11 z-50 w-72 rounded-2xl border border-line bg-surface p-4 shadow-panel animate-in fade-in slide-in-from-top-2 duration-150">
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
              <div className="mb-2 grid grid-cols-7 text-center text-[11px] font-semibold text-ink-muted">
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

        {/* Live Clock Widget */}
        <div className="flex items-center gap-1.5 rounded-xl border border-line bg-surface px-3 py-1.5 text-xs font-mono font-medium text-ink shadow-xs">
          <Clock size={14} className="text-brand-600 shrink-0" />
          <span>{liveTime || "08:30"}</span>
        </div>

        {/* Notification Bell Widget */}
        <div className="relative">
          <button
            type="button"
            onClick={toggleNotif}
            aria-label="Thông báo"
            className="relative grid size-9 place-items-center rounded-xl border border-line bg-surface text-ink-muted transition-all hover:bg-surface-muted hover:text-ink shadow-xs"
          >
            <Bell size={16} />
            {unreadCount > 0 && (
              <span className="absolute -right-1 -top-1 flex size-4 items-center justify-center rounded-full bg-danger text-[10px] font-bold text-white shadow-xs">
                {unreadCount}
              </span>
            )}
          </button>

          {/* Notifications Popover */}
          {notifOpen && (
            <div className="absolute right-0 top-11 z-50 w-80 rounded-2xl border border-line bg-surface p-4 shadow-panel space-y-3 animate-in fade-in slide-in-from-top-2 duration-150">
              <div className="flex items-center justify-between border-b border-line pb-2">
                <span className="text-xs font-bold text-ink">Thông báo mới</span>
                {unreadCount > 0 && (
                  <button
                    onClick={markAllRead}
                    className="text-[11px] font-medium text-brand-600 hover:underline"
                  >
                    Đánh dấu đã đọc
                  </button>
                )}
              </div>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {notifications.map((n) => (
                  <div
                    key={n.id}
                    className={`flex items-start gap-2.5 rounded-xl p-2.5 text-xs transition-colors ${
                      n.unread ? "bg-brand-50/70" : "bg-surface-muted"
                    }`}
                  >
                    {n.type === "info" && <Info size={15} className="mt-0.5 text-brand-600 shrink-0" />}
                    {n.type === "success" && <CheckCircle2 size={15} className="mt-0.5 text-success shrink-0" />}
                    {n.type === "alert" && <AlertCircle size={15} className="mt-0.5 text-danger shrink-0" />}
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-ink leading-tight">{n.title}</p>
                      <span className="text-[10px] text-ink-muted">{n.time}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Staff Profile Card */}
        <div className="flex items-center gap-2 rounded-xl border border-line bg-surface p-1.5 pl-2 shadow-xs">
          <div className="grid size-7 shrink-0 place-items-center rounded-full bg-brand-100 text-xs font-bold text-brand-700">
            {staffInitials}
          </div>
          <div className="hidden lg:block min-w-0 pr-1 text-left">
            <span className="block truncate text-xs font-bold text-ink leading-none">
              {staffName}
            </span>
            <span className="block text-[10px] font-medium text-ink-muted leading-none mt-0.5">
              {ROLE_LABEL[role]}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
}
