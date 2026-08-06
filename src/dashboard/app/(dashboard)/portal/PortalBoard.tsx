"use client";

// Command Center — Cổng trung tâm điều khiển toàn hệ thống.
// Tổng hợp mọi thứ: trạng thái hệ thống, vai trò, màn hình, hạ tầng, nhân viên.

// Nhập component Link từ Next.js để tạo liên kết nội bộ
import Link from "next/link";
// Nhập hằng số VN_TZ (múi giờ Việt Nam) từ file datetime
import { VN_TZ } from "../../../lib/datetime";
// Nhập các hook useCallback, useEffect, useState từ React
import { useCallback, useEffect, useState } from "react";
// Nhập các icon từ thư viện lucide-react
import {
  Activity, // Icon hoạt động
  AlertTriangle, // Icon cảnh báo tam giác
  BarChart3, // Icon biểu đồ
  CheckCircle2, // Icon dấu check tròn
  Clock3, // Icon đồng hồ
  Database, // Icon cơ sở dữ liệu
  ExternalLink, // Icon liên kết ngoài
  FileClock, // Icon file đồng hồ
  Gauge, // Icon đồng hồ đo
  HardDrive, // Icon ổ cứng
  LayoutDashboard, // Icon bảng điều khiển
  RefreshCw, // Icon làm mới
  ScrollText, // Icon cuộn văn bản
  Settings, // Icon cài đặt
  ShieldCheck, // Icon khiên bảo mật
  Users, // Icon người dùng
  XCircle, // Icon X tròn
  Zap, // Icon tia sét
  type LucideIcon, // Kiểu dữ liệu cho icon
} from "lucide-react";

// Nhập các hàm và kiểu dữ liệu từ file ops-summary
import {
  emptyOpsSummary, // Hàm tạo summary rỗng
  normalizeOpsPayload, // Hàm chuẩn hóa dữ liệu ops
  safeHttpUrl, // Hàm kiểm tra URL an toàn
  type OpsLinks, // Kiểu dữ liệu liên kết ops
  type OpsSummary, // Kiểu dữ liệu summary ops
  type ServiceState, // Kiểu dữ liệu trạng thái dịch vụ
} from "../../../lib/ops-summary";
// Nhập các hằng số và hàm liên quan đến vai trò
import {
  ALL_ROLES, // Danh sách tất cả vai trò
  ROLE_LABEL, // Bảng nhãn vai trò
  canSeeNav, // Hàm kiểm tra quyền xem màn hình
  type ClinicRole, // Kiểu dữ liệu vai trò phòng khám
} from "../../../lib/roles";
// Nhập danh sách điều hướng NAV
import { NAV } from "../nav-items";

// ─── Types ────────────────────────────────────────────────────────────────────
// ─── Kiểu dữ liệu ─────────────────────────────────────────────────────────────

// Định nghĩa interface cho một dòng nhân viên
interface StaffRow {
  id: string; // ID của nhân viên
  full_name: string; // Tên đầy đủ
  short_name: string | null; // Tên viết tắt, có thể null
  primary_department: string; // Phòng ban chính
  employment_type: string; // Loại hợp đồng
  is_active: boolean; // Có đang hoạt động không
  auth_user_id: string | null; // ID người dùng xác thực, có thể null
}

// Định nghĩa interface cho một sự kiện gần đây
interface RecentEvent {
  event_id: string; // ID của sự kiện
  event_type: string; // Loại sự kiện
  aggregate_type: string; // Loại đối tượng
  source: string; // Nguồn ghi
  occurred_at: string; // Thời gian xảy ra
}

// Định nghĩa interface cho props (dữ liệu truyền vào component)
interface PortalProps {
  staff: StaffRow[]; // Danh sách nhân viên
  counts: { // Các số liệu đếm
    appointmentsToday: number; // Số lịch hẹn hôm nay
    patientsToday: number; // Số bệnh nhân mới hôm nay
    visitsToday: number; // Số lượt khám hôm nay
    pendingTasks: number; // Số việc đang chờ
  };
  recentEvents: RecentEvent[]; // Danh sách sự kiện gần đây
}

// ─── Constants ────────────────────────────────────────────────────────────────
// ─── Hằng số ──────────────────────────────────────────────────────────────────

// Bảng nhãn tiếng Việt cho các dịch vụ
const SERVICE_LABELS: Record<string, string> = {
  api: "FastAPI", // Dịch vụ API backend
  dashboard: "Dashboard", // Dịch vụ dashboard
  caddy: "Caddy ingress", // Dịch vụ Caddy (proxy)
  worker: "Worker", // Dịch vụ worker
  "notification-relay": "Notification relay", // Dịch vụ chuyển tiếp thông báo
  rabbitmq: "RabbitMQ", // Dịch vụ message queue
  dozzle: "Dozzle", // Dịch vụ xem log
  "uptime-kuma": "Uptime Kuma", // Dịch vụ theo dõi uptime
};

// Bảng style CSS cho từng trạng thái
const STATE_STYLE: Record<string, string> = {
  healthy: "border-success bg-success-bg text-success", // Trạng thái khỏe mạnh - màu xanh
  degraded: "border-warning bg-warning-bg text-warning", // Trạng thái suy giảm - màu vàng
  critical: "border-danger bg-danger-bg text-danger", // Trạng thái nguy kịch - màu đỏ
  down: "border-danger bg-danger-bg text-danger", // Trạng thái mất kết nối - màu đỏ
  unknown: "border-line bg-surface-muted text-ink-muted", // Trạng thái không rõ - màu xám
  disabled: "border-line bg-surface-sunken text-ink-faint", // Trạng thái tắt - màu nhạt
  fresh: "border-success bg-success-bg text-success", // Còn mới - màu xanh
  stale: "border-warning bg-warning-bg text-warning", // Sắp quá hạn - màu vàng
  expired: "border-danger bg-danger-bg text-danger", // Quá hạn - màu đỏ
  invalid: "border-danger bg-danger-bg text-danger", // Không hợp lệ - màu đỏ
  good: "border-success bg-success-bg text-success", // Tốt - màu xanh
  warning: "border-warning bg-warning-bg text-warning", // Cảnh báo - màu vàng
};

// Mô tả ngắn cho từng vai trò
const ROLE_DESC: Record<ClinicRole, string> = {
  DOCTOR: "Khám, chẩn đoán, kê đơn", // Bác sĩ
  ULTRASOUND_DOCTOR: "Siêu âm, đo chỉ số thai", // Bác sĩ siêu âm
  NURSE_ULTRASOUND: "Hỗ trợ siêu âm, xét nghiệm", // Điều dưỡng siêu âm
  TKYK: "Nhập hồ sơ lâm sàng hộ bác sĩ", // Thư ký y khoa
  CSKH: "Chăm sóc khách hàng, đặt lịch", // Chăm sóc khách hàng
  MANAGEMENT: "Quản lý toàn hệ thống", // Quản lý
  RECEPTION: "Đón tiếp, check-in, hành chính", // Lễ tân
  CASHIER: "Thu ngân tổng hợp", // Thu ngân tổng hợp
  CASHIER_THUOC: "Thu ngân bán thuốc", // Thu ngân bán thuốc
  CASHIER_DV: "Thu ngân dịch vụ", // Thu ngân dịch vụ
  TRUONG_CA: "Điều phối ca, vận hành", // Trưởng ca
  PHARMACIST: "Dược sĩ, cấp phát thuốc", // Dược sĩ  // Không hiện ở cổng chọn vai — đây là tài khoản của cái tivi, không
  // phải của một người.
  DISPLAY: "Bảng gọi số phòng chờ",
};

// ─── Helpers ──────────────────────────────────────────────────────────────────
// ─── Hàm trợ giúp ─────────────────────────────────────────────────────────────

// Component hiển thị icon theo trạng thái
function StateIcon({ state }: { state: string }) {
  // Nếu trạng thái là khỏe mạnh/mới/tốt thì hiển thị icon check
  if (["healthy", "fresh", "good"].includes(state)) {
    return <CheckCircle2 size={16} aria-hidden />;
  }
  // Nếu trạng thái là nguy kịch/mất kết nối/quá hạn/không hợp lệ thì hiển thị icon X
  if (["critical", "down", "expired", "invalid"].includes(state)) {
    return <XCircle size={16} aria-hidden />;
  }
  // Các trạng thái khác hiển thị icon cảnh báo
  return <AlertTriangle size={16} aria-hidden />;
}

// Component hiển thị badge (nhãn) với màu theo trạng thái
function Badge({ state, text }: { state: string; text: string }) {
  return (
    // Span với style theo trạng thái
    <span
      className={`inline-flex items-center gap-1.5 rounded-chip border px-2.5 py-1 text-xs font-medium ${STATE_STYLE[state] ?? STATE_STYLE.unknown}`}
    >
      {/* Icon trạng thái */}
      <StateIcon state={state} />
      {/* Văn bản badge */}
      {text}
    </span>
  );
}

// Hàm định dạng số theo tiếng Việt
function fmtNumber(value: number | null, suffix = "") {
  return value === null
    ? "—" // Nếu null thì hiển thị dấu gạch ngang
    : `${new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 1 }).format(value)}${suffix}`; // Định dạng số với tối đa 1 chữ số thập phân
}

// Hàm định dạng dung lượng byte
function fmtBytes(value: number | null) {
  if (value === null) return "—"; // Nếu null thì hiển thị dấu gạch ngang
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`; // Nếu dưới 1MB thì hiển thị KB
  return `${(value / 1024 / 1024).toFixed(1)} MB`; // Nếu trên 1MB thì hiển thị MB
}

// Hàm định dạng ngày giờ theo múi giờ Việt Nam
function fmtDateTime(iso: string) {
  return new Date(iso).toLocaleString("vi-VN", {
    day: "2-digit", // Ngày 2 chữ số
    month: "2-digit", // Tháng 2 chữ số
    hour: "2-digit", // Giờ 2 chữ số
    minute: "2-digit", // Phút 2 chữ số
    timeZone: VN_TZ, // Múi giờ Việt Nam
  });
}

// ─── Sub-components ───────────────────────────────────────────────────────────
// ─── Component con ────────────────────────────────────────────────────────────

// Component SectionCard — thẻ chứa một phần nội dung với tiêu đề và icon
function SectionCard({
  title, // Tiêu đề của phần
  icon: Icon, // Icon của phần
  children, // Nội dung bên trong
  className = "", // Class CSS tùy chỉnh
}: {
  title: string;
  icon: LucideIcon;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    // Thẻ section với style card
    <section
      className={`rounded-card border border-line bg-surface p-4 shadow-card ${className}`}
    >
      {/* Tiêu đề với icon */}
      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
        <Icon size={17} className="text-brand-600" />
        {title}
      </h2>
      {/* Nội dung bên trong */}
      {children}
    </section>
  );
}

// Component StatTile — thẻ hiển thị một số liệu thống kê
function StatTile({
  label, // Nhãn của số liệu
  value, // Giá trị số
  icon: Icon, // Icon
  accent = "text-brand-600", // Màu nhấn
}: {
  label: string;
  value: number;
  icon: LucideIcon;
  accent?: string;
}) {
  return (
    // Thẻ hiển thị số liệu
    <div className="rounded-card border border-line bg-surface p-4 shadow-card">
      {/* Hàng trên: nhãn + icon */}
      <div className="flex items-center justify-between">
        <p className="text-xs text-ink-muted">{label}</p>
        <Icon size={18} className={accent} aria-hidden />
      </div>
      {/* Giá trị số lớn */}
      <p className="mt-1 text-2xl font-semibold text-ink">{value}</p>
    </div>
  );
}

// Component ServiceCard — thẻ hiển thị trạng thái một dịch vụ
function ServiceCard({
  label, // Tên dịch vụ
  state, // Trạng thái
  latency, // Độ trễ (ms)
  restarts, // Số lần khởi động lại
}: {
  label: string;
  state: ServiceState;
  latency?: number | null;
  restarts?: number;
}) {
  // Chuyển đổi trạng thái sang văn bản tiếng Việt
  const stateText =
    state === "healthy"
      ? "Ổn định" // Trạng thái khỏe mạnh
      : state === "disabled"
        ? "Đang tắt" // Trạng thái tắt
        : state === "down"
          ? "Mất kết nối" // Trạng thái mất kết nối
          : "Chưa rõ"; // Trạng thái không rõ
  return (
    // Thẻ hiển thị dịch vụ
    <div className="flex items-center justify-between rounded-control border border-line bg-surface-muted px-3 py-2.5">
      {/* Phần thông tin dịch vụ */}
      <div className="min-w-0">
        {/* Tên dịch vụ */}
        <p className="truncate text-sm font-medium text-ink">{label}</p>
        {/* Độ trễ hoặc số lần restart */}
        <p className="text-xs text-ink-muted">
          {latency !== undefined
            ? `Độ trễ ${fmtNumber(latency, " ms")}` // Hiển thị độ trễ
            : `Restart ${restarts ?? 0}`} {/* Hiển thị số lần restart */}
        </p>
      </div>
      {/* Badge trạng thái */}
      <Badge state={state} text={stateText} />
    </div>
  );
}

// Component ToolLink — liên kết đến công cụ chuyên sâu
function ToolLink({
  href, // URL liên kết
  title, // Tiêu đề
  detail, // Mô tả chi tiết
  icon, // Icon
}: {
  href: string | null;
  title: string;
  detail: string;
  icon: React.ReactNode;
}) {
  // Nếu chưa có URL
  if (!href) {
    return (
      // Hiển thị thẻ không có liên kết
      <div className="flex items-center gap-3 rounded-card border border-dashed border-line bg-surface-muted p-4 text-ink-muted">
        {icon}
        <div>
          <p className="text-sm font-medium">{title}</p>
          <p className="text-xs">Chưa cấu hình đường dẫn an toàn.</p>
        </div>
      </div>
    );
  }
  return (
    // Liên kết ngoài đến công cụ
    <a
      href={href} // URL đích
      target="_blank" // Mở tab mới
      rel="noopener noreferrer" // Bảo mật khi mở tab mới
      className="group flex items-center gap-3 rounded-card border border-line bg-surface p-4 shadow-card transition hover:border-brand-300 hover:bg-brand-50"
    >
      {/* Icon trong khung */}
      <span className="rounded-control bg-brand-50 p-2 text-brand-600">
        {icon}
      </span>
      {/* Tiêu đề và mô tả */}
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-ink">{title}</p>
        <p className="text-xs text-ink-muted">{detail}</p>
      </div>
      {/* Icon liên kết ngoài */}
      <ExternalLink
        size={16}
        className="text-ink-faint group-hover:text-brand-600"
        aria-hidden
      />
    </a>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────
// ─── Component chính ──────────────────────────────────────────────────────────

// Component chính PortalBoard — Cổng trung tâm điều khiển
export default function PortalBoard({
  staff, // Danh sách nhân viên
  counts, // Các số liệu đếm
  recentEvents, // Sự kiện gần đây
}: PortalProps) {
  // State lưu summary trạng thái hệ thống (khởi tạo rỗng)
  const [summary, setSummary] = useState<OpsSummary>(emptyOpsSummary());
  // State lưu các liên kết công cụ
  const [links, setLinks] = useState<OpsLinks>({
    logs: null, // Liên kết log
    uptime: null, // Liên kết uptime
    sentry: null, // Liên kết sentry
  });
  // State lưu trạng thái đang tải
  const [loading, setLoading] = useState(true);
  // State lưu trạng thái nguồn không khả dụng
  const [sourceUnavailable, setSourceUnavailable] = useState(false);

  // Hàm refresh dữ liệu ops từ API (dùng useCallback để tối ưu)
  const refresh = useCallback(async () => {
    setLoading(true); // Bật trạng thái đang tải
    try {
      // Gọi API lấy summary ops
      const response = await fetch("/api/ops/summary", { cache: "no-store" });
      if (!response.ok) throw new Error("ops unavailable"); // Nếu lỗi thì ném exception
      const payload = (await response.json()) as Record<string, unknown>; // Parse JSON
      setSummary(normalizeOpsPayload(payload)); // Chuẩn hóa và lưu summary
      // Lấy các liên kết từ payload
      const rawLinks =
        payload.links && typeof payload.links === "object"
          ? (payload.links as Record<string, unknown>)
          : {};
      // Lưu các liên kết đã kiểm tra an toàn
      setLinks({
        logs: safeHttpUrl(
          typeof rawLinks.logs === "string" ? rawLinks.logs : null,
        ),
        uptime: safeHttpUrl(
          typeof rawLinks.uptime === "string" ? rawLinks.uptime : null,
        ),
        sentry: safeHttpUrl(
          typeof rawLinks.sentry === "string" ? rawLinks.sentry : null,
        ),
      });
      // Lưu trạng thái nguồn không khả dụng
      setSourceUnavailable(payload.sourceUnavailable === true);
    } catch {
      // Nếu có lỗi thì reset summary và báo nguồn không khả dụng
      setSummary(emptyOpsSummary());
      setSourceUnavailable(true);
    } finally {
      setLoading(false); // Tắt trạng thái đang tải
    }
  }, []); // Không có dependency — chỉ tạo một lần

  // useEffect quản lý việc tự động refresh
  useEffect(() => {
    // Refresh ngay lập tức khi mount
    const initial = window.setTimeout(() => void refresh(), 0);
    // Tạo interval refresh mỗi 30 giây
    const timer = window.setInterval(() => {
      // Chỉ refresh khi tab đang hiển thị
      if (document.visibilityState === "visible") void refresh();
    }, 30_000);
    // Hàm xử lý khi tab chuyển sang hiển thị
    const onVisible = () => {
      if (document.visibilityState === "visible") void refresh();
    };
    // Lắng nghe sự kiện thay đổi hiển thị
    document.addEventListener("visibilitychange", onVisible);
    // Cleanup: xóa timeout, interval và event listener
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [refresh]); // Chỉ chạy lại khi refresh thay đổi

  // Chuyển đổi trạng thái tổng thể sang văn bản tiếng Việt
  const overallText =
    summary.overall === "healthy"
      ? "Hệ thống ổn định" // Trạng thái khỏe mạnh
      : summary.overall === "critical"
        ? "Cần xử lý ngay" // Trạng thái nguy kịch
        : "Có hạng mục cần kiểm tra"; // Trạng thái khác
  // Lấy style cho trạng thái tổng thể
  const overallStyle = STATE_STYLE[summary.overall] ?? STATE_STYLE.unknown;

  // Nhóm màn hình theo vai trò
  const roleScreens = ALL_ROLES.map((r) => {
    // Lọc các màn hình mà vai trò này có thể xem
    const screens = NAV.filter((item) => {
      // /portal không hiển thị trong grid vai trò
      if (item.href === "/portal") return false;
      return canSeeNav(r, item.href); // Kiểm tra quyền xem
    });
    return { role: r, screens }; // Trả về vai trò và danh sách màn hình
  });

  // Số nhân viên active / đã link
  const activeStaff = staff.filter((s) => s.is_active).length; // Đếm nhân viên đang hoạt động
  const linkedStaff = staff.filter((s) => s.auth_user_id !== null).length; // Đếm nhân viên đã link login

  return (
    // Container chính của trang
    <main className="page-in min-w-0 space-y-6 p-4 lg:p-5">
      {/* ── Header ─────────────────────────────────────────────────────── */}
      {/* ── Phần đầu trang ─────────────────────────────────────────────── */}
      <header className="flex flex-wrap items-start justify-between gap-3">
        {/* Phần tiêu đề */}
        <div>
          {/* Icon + tên trang */}
          <div className="flex items-center gap-2">
            <Zap size={22} className="text-brand-600" />
            <h1 className="text-xl font-semibold text-ink lg:text-2xl">
              Command Center
            </h1>
          </div>
          {/* Mô tả trang */}
          <p className="mt-1 text-sm text-ink-muted">
            Cổng trung tâm điều khiển toàn hệ thống · vai trò, màn hình, hạ
            tầng, vận hành
          </p>
        </div>
        {/* Nút làm mới */}
        <button
          type="button"
          onClick={() => void refresh()} // Gọi hàm refresh khi click
          disabled={loading} // Vô hiệu hóa khi đang tải
          className="inline-flex items-center gap-2 rounded-control border border-line bg-surface px-3 py-2 text-sm font-medium text-ink-soft shadow-card hover:bg-surface-muted disabled:opacity-60"
        >
          {/* Icon làm mới, xoay khi đang tải */}
          <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
          Làm mới
        </button>
      </header>

      {/* ── Tổng quan hệ thống ─────────────────────────────────────────── */}
      {/* ── Phần tổng quan trạng thái hệ thống ─────────────────────────── */}
      <section
        className={`flex flex-wrap items-center justify-between gap-4 rounded-card border p-4 shadow-card ${overallStyle}`}
      >
        {/* Phần trạng thái tổng thể */}
        <div className="flex items-center gap-3">
          {/* Icon trạng thái */}
          <StateIcon state={summary.overall} />
          <div>
            {/* Văn bản trạng thái */}
            <p className="font-semibold">{overallText}</p>
            {/* Chi tiết snapshot */}
            <p className="text-xs opacity-80">
              {sourceUnavailable
                ? "Nguồn trạng thái tạm thời chưa phản hồi." // Nguồn không khả dụng
                : `Snapshot ${summary.snapshotState} · ${summary.environment}`} {/* Thông tin snapshot và môi trường */}
            </p>
          </div>
        </div>
        {/* Thời gian cập nhật */}
        <div className="flex items-center gap-2 text-xs">
          <Clock3 size={15} />
          Cập nhật{" "}
          {summary.generatedAt === new Date(0).toISOString()
            ? "—" // Nếu chưa có thời gian thì hiển thị dấu gạch ngang
            : new Date(summary.generatedAt).toLocaleTimeString("vi-VN")} {/* Hiển thị thời gian cập nhật */}
        </div>
      </section>

      {/* ── Số liệu hôm nay ────────────────────────────────────────────── */}
      {/* ── Phần số liệu thống kê hôm nay ──────────────────────────────── */}
      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {/* Thẻ: số lịch hẹn hôm nay */}
        <StatTile
          label="Lịch hẹn hôm nay"
          value={counts.appointmentsToday}
          icon={BarChart3}
        />
        {/* Thẻ: số bệnh nhân mới hôm nay */}
        <StatTile
          label="BN mới hôm nay"
          value={counts.patientsToday}
          icon={Users}
        />
        {/* Thẻ: số lượt khám hôm nay */}
        <StatTile
          label="Lượt khám hôm nay"
          value={counts.visitsToday}
          icon={Activity}
        />
        {/* Thẻ: số việc đang chờ */}
        <StatTile
          label="Việc đang chờ"
          value={counts.pendingTasks}
          icon={Clock3}
          accent="text-warning"
        />
      </section>

      {/* ── Dịch vụ & hiệu năng ────────────────────────────────────────── */}
      {/* ── Phần dịch vụ và hiệu năng hệ thống ─────────────────────────── */}
      <SectionCard title="Dịch vụ & hiệu năng" icon={Activity}>
        {/* Lưới hiển thị các dịch vụ */}
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          {/* Thẻ database */}
          <ServiceCard
            label="Database"
            state={summary.database.state}
            latency={summary.database.latencyMs}
          />
          {/* Lặp qua từng dịch vụ */}
          {summary.services.map((service) => (
            <ServiceCard
              key={service.id} // Key duy nhất
              label={SERVICE_LABELS[service.id] ?? service.id} // Nhãn dịch vụ
              state={service.state} // Trạng thái
              restarts={service.restartCount} // Số lần restart
            />
          ))}
          {/* Nếu không có dịch vụ nào thì hiển thị host collector */}
          {summary.services.length === 0 && (
            <ServiceCard label="Host collector" state="unknown" restarts={0} />
          )}
        </div>
      </SectionCard>

      {/* ── Backup & tài nguyên ────────────────────────────────────────── */}
      {/* ── Phần backup và tài nguyên hệ thống ─────────────────────────── */}
      <div className="grid gap-5 xl:grid-cols-2">
        {/* Phần backup và tài nguyên */}
        <SectionCard title="Backup & tài nguyên" icon={FileClock}>
          <div className="grid gap-3 sm:grid-cols-2">
            {/* Thẻ: backup gần nhất */}
            <div className="rounded-control border border-line bg-surface-muted p-3">
              <p className="text-xs text-ink-muted">Backup gần nhất</p>
              {/* Số giờ kể từ backup */}
              <p className="mt-1 text-lg font-semibold text-ink">
                {summary.backup.ageHours === null
                  ? "Chưa rõ" // Nếu chưa có dữ liệu
                  : `${fmtNumber(summary.backup.ageHours)} giờ trước`} {/* Số giờ trước */}
              </p>
              {/* Badge trạng thái backup */}
              <div className="mt-2">
                <Badge
                  state={summary.backup.state}
                  text={
                    summary.backup.state === "fresh"
                      ? "Còn mới" // Backup còn mới
                      : summary.backup.state === "stale"
                        ? "Sắp quá hạn" // Backup sắp quá hạn
                        : summary.backup.state === "critical"
                          ? "Quá hạn/lỗi" // Backup quá hạn hoặc lỗi
                          : "Chưa có dữ liệu" // Chưa có dữ liệu
                  }
                />
              </div>
            </div>
            {/* Thẻ: dung lượng backup */}
            <div className="rounded-control border border-line bg-surface-muted p-3">
              <p className="text-xs text-ink-muted">Dung lượng backup</p>
              {/* Dung lượng backup */}
              <p className="mt-1 text-lg font-semibold text-ink">
                {fmtBytes(summary.backup.archiveBytes)}
              </p>
              {/* Ghi chú */}
              <p className="mt-2 text-xs text-ink-muted">
                Public schema · cần Supabase PITR/Auth riêng
              </p>
            </div>
            {/* Thẻ: SSD đã dùng */}
            <div className="rounded-control border border-line bg-surface-muted p-3">
              <p className="flex items-center gap-1.5 text-xs text-ink-muted">
                <HardDrive size={14} /> SSD đã dùng
              </p>
              {/* Phần trăm SSD đã dùng */}
              <p className="mt-1 text-lg font-semibold text-ink">
                {fmtNumber(summary.host?.diskUsedPercent ?? null, "%")}
              </p>
            </div>
            {/* Thẻ: log 15 phút */}
            <div className="rounded-control border border-line bg-surface-muted p-3">
              <p className="text-xs text-ink-muted">Log 15 phút</p>
              {/* Số lỗi và cảnh báo */}
              <p className="mt-1 text-lg font-semibold text-ink">
                {summary.logCounts
                  ? `${summary.logCounts.errors} lỗi · ${summary.logCounts.warnings} cảnh báo`
                  : "Chưa rõ"} {/* Nếu chưa có dữ liệu */}
              </p>
              {/* Ghi chú */}
              <p className="mt-2 text-xs text-ink-muted">
                Chỉ đếm mức độ, không đọc nội dung log.
              </p>
            </div>
          </div>
        </SectionCard>

        {/* ── Bảo mật ──────────────────────────────────────────────────── */}
        {/* ── Phần bảo mật hệ thống ────────────────────────────────────── */}
        <SectionCard title="Bảo mật" icon={ShieldCheck}>
          <ul className="space-y-2">
            {/* Nếu có các mục bảo mật */}
            {summary.security.length > 0 ? (
              // Lặp qua từng mục bảo mật
              summary.security.map((item) => (
                <li
                  key={item.id} // Key duy nhất
                  className="flex items-start gap-3 rounded-control border border-line bg-surface-muted p-3"
                >
                  {/* Icon trạng thái */}
                  <span
                    className={`mt-0.5 rounded-chip border p-1.5 ${STATE_STYLE[item.state] ?? STATE_STYLE.unknown}`}
                  >
                    <StateIcon state={item.state} />
                  </span>
                  {/* Nội dung mục bảo mật */}
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-ink">
                      {item.label}
                    </p>
                    <p className="mt-0.5 text-xs leading-5 text-ink-muted">
                      {item.detail}
                    </p>
                  </div>
                </li>
              ))
            ) : (
              // Nếu không có dữ liệu bảo mật
              <li className="flex items-start gap-3 rounded-control border border-line bg-surface-muted p-3">
                <span
                  className={`mt-0.5 rounded-chip border p-1.5 ${STATE_STYLE.unknown}`}
                >
                  <StateIcon state="unknown" />
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-ink">
                    Kiểm tra host
                  </p>
                  <p className="mt-0.5 text-xs leading-5 text-ink-muted">
                    Chưa có snapshot host hợp lệ; không tự giả định trạng thái
                    an toàn.
                  </p>
                </div>
              </li>
            )}
          </ul>
        </SectionCard>
      </div>

      {/* ── Vai trò & Màn hình ─────────────────────────────────────────── */}
      {/* ── Phần vai trò và màn hình ───────────────────────────────────── */}
      <SectionCard title="Vai trò & Màn hình" icon={LayoutDashboard}>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {/* Lặp qua từng vai trò và danh sách màn hình */}
          {roleScreens.map(({ role: r, screens }) => (
            <div
              key={r} // Key duy nhất cho mỗi vai trò
              className="rounded-card border border-line bg-surface-muted p-4"
            >
              {/* Phần đầu: tên vai trò + số màn hình */}
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  {/* Tên vai trò */}
                  <p className="text-sm font-semibold text-ink">
                    {ROLE_LABEL[r]}
                  </p>
                  {/* Mô tả vai trò */}
                  <p className="mt-0.5 text-xs text-ink-muted">
                    {ROLE_DESC[r]}
                  </p>
                </div>
                {/* Số màn hình */}
                <span className="shrink-0 rounded-full bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">
                  {screens.length} màn
                </span>
              </div>
              {/* Danh sách các màn hình */}
              <div className="mt-3 flex flex-wrap gap-1.5">
                {/* Lặp qua từng màn hình */}
                {screens.map((item) => (
                  <Link
                    key={item.href} // Key duy nhất
                    href={item.href} // Đường dẫn
                    className="inline-flex items-center gap-1 rounded-chip border border-line bg-surface px-2 py-1 text-xs text-ink-soft transition hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700"
                  >
                    <item.icon size={12} aria-hidden />
                    {item.shortLabel ?? item.label} {/* Nhãn ngắn hoặc nhãn đầy đủ */}
                  </Link>
                ))}
                {/* Nếu không có màn hình nào */}
                {screens.length === 0 && (
                  <span className="text-xs text-ink-faint">
                    Không có màn hình riêng
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </SectionCard>

      {/* ── Nhân viên ──────────────────────────────────────────────────── */}
      {/* ── Phần danh sách nhân viên ───────────────────────────────────── */}
      <SectionCard title="Nhân viên" icon={Users}>
        {/* Các badge thống kê nhân viên */}
        <div className="mb-3 flex flex-wrap items-center gap-3 text-sm">
          {/* Tổng số nhân viên */}
          <span className="rounded-chip border border-line bg-surface-muted px-3 py-1.5">
            <span className="font-semibold text-ink">{staff.length}</span>{" "}
            <span className="text-ink-muted">tổng</span>
          </span>
          {/* Số nhân viên active */}
          <span className="rounded-chip border border-success bg-success-bg px-3 py-1.5 text-success">
            <span className="font-semibold">{activeStaff}</span> active
          </span>
          {/* Số nhân viên đã link login */}
          <span className="rounded-chip border border-warning bg-warning-bg px-3 py-1.5 text-warning">
            <span className="font-semibold">{linkedStaff}</span> đã link login
          </span>
        </div>
        {/* Bảng danh sách nhân viên */}
        <div className="max-h-80 overflow-y-auto rounded-control border border-line">
          <table className="min-w-full divide-y divide-brand-100 text-sm">
            {/* Tiêu đề bảng, cố định khi cuộn */}
            <thead className="sticky top-0 z-10 bg-brand-100 text-left text-[11px] font-semibold uppercase tracking-wide text-brand-800">
              <tr>
                <th className="px-4 py-2.5 font-medium">Họ tên</th> {/* Cột họ tên */}
                <th className="px-4 py-2.5 font-medium">Vai trò</th> {/* Cột vai trò */}
                <th className="px-4 py-2.5 font-medium">Hợp đồng</th> {/* Cột hợp đồng */}
                <th className="px-4 py-2.5 font-medium">Trạng thái</th> {/* Cột trạng thái */}
              </tr>
            </thead>
            {/* Thân bảng */}
            <tbody className="divide-y divide-brand-100">
              {/* Lặp qua từng nhân viên */}
              {staff.map((s) => (
                <tr
                  key={s.id} // Key duy nhất
                  className="transition-colors duration-150 hover:bg-brand-50"
                >
                  {/* Cột họ tên */}
                  <td className="px-4 py-2.5 text-ink">
                    {s.full_name}
                    {/* Tên viết tắt nếu khác tên đầy đủ */}
                    {s.short_name && s.short_name !== s.full_name && (
                      <span className="ml-2 text-xs text-ink-muted">
                        {s.short_name}
                      </span>
                    )}
                  </td>
                  {/* Cột vai trò */}
                  <td className="px-4 py-2.5 text-ink-soft">
                    {ROLE_LABEL[s.primary_department as ClinicRole] ??
                      s.primary_department}
                  </td>
                  {/* Cột loại hợp đồng */}
                  <td className="px-4 py-2.5 text-xs text-ink-muted">
                    {s.employment_type}
                  </td>
                  {/* Cột trạng thái */}
                  <td className="px-4 py-2.5">
                    {/* Trạng thái active/inactive */}
                    {s.is_active ? (
                      <span className="inline-flex items-center gap-1 text-xs text-success">
                        <span className="h-1.5 w-1.5 rounded-full bg-success" />
                        Active
                      </span>
                    ) : (
                      <span className="text-xs text-ink-muted">Inactive</span>
                    )}
                    {/* Trạng thái đã link login */}
                    {s.auth_user_id ? (
                      <span className="ml-2 inline-flex items-center gap-1 text-xs text-success">
                        <span className="h-1.5 w-1.5 rounded-full bg-success" />
                        Đã link
                      </span>
                    ) : (
                      <span className="ml-2 inline-flex items-center gap-1 text-xs text-warning">
                        <span className="h-1.5 w-1.5 rounded-full bg-warning" />
                        Chưa link
                      </span>
                    )}
                  </td>
                </tr>
              ))}
              {/* Nếu không có nhân viên nào */}
              {staff.length === 0 && (
                <tr>
                  <td
                    colSpan={4} // Trải rộng 4 cột
                    className="px-4 py-6 text-center text-ink-muted"
                  >
                    Chưa có nhân viên.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </SectionCard>

      {/* ── Sự kiện gần đây ────────────────────────────────────────────── */}
      {/* ── Phần sự kiện gần đây ───────────────────────────────────────── */}
      <SectionCard title="Sự kiện gần đây" icon={ScrollText}>
        {/* Nếu không có sự kiện */}
        {recentEvents.length === 0 ? (
          <p className="py-6 text-center text-sm text-ink-muted">
            Chưa có sự kiện nào.
          </p>
        ) : (
          // Danh sách sự kiện
          <ul className="space-y-1.5">
            {/* Lặp qua từng sự kiện */}
            {recentEvents.map((e) => (
              <li
                key={e.event_id} // Key duy nhất
                className="flex items-start gap-3 rounded-control border border-line bg-surface-muted px-3 py-2"
              >
                {/* Thời gian xảy ra */}
                <span className="mt-0.5 shrink-0 text-xs tabular-nums text-ink-faint">
                  {fmtDateTime(e.occurred_at)}
                </span>
                {/* Nội dung sự kiện */}
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    {/* Badge loại sự kiện */}
                    <span className="rounded-full bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">
                      {e.event_type}
                    </span>
                    {/* Loại đối tượng và nguồn */}
                    <span className="text-xs text-ink-muted">
                      {e.aggregate_type} · {e.source}
                    </span>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      {/* ── Công cụ chuyên sâu ─────────────────────────────────────────── */}
      {/* ── Phần công cụ chuyên sâu ────────────────────────────────────── */}
      <SectionCard title="Công cụ chuyên sâu" icon={Settings}>
        <div className="grid gap-3 md:grid-cols-3">
          {/* Liên kết đến Dozzle (log) */}
          <ToolLink
            href={links.logs}
            title="Log realtime · Dozzle"
            detail="Mở ở tab riêng, không đưa log bệnh nhân vào dashboard."
            icon={<ScrollText size={18} />}
          />
          {/* Liên kết đến Uptime Kuma */}
          <ToolLink
            href={links.uptime}
            title="Uptime Kuma"
            detail="Theo dõi uptime và cấu hình cảnh báo."
            icon={<Activity size={18} />}
          />
          {/* Liên kết đến Sentry */}
          <ToolLink
            href={links.sentry}
            title="Sentry"
            detail="Điều tra exception theo request ID."
            icon={<Database size={18} />}
          />
        </div>
      </SectionCard>

      {/* ── Lối tắt quản trị ───────────────────────────────────────────── */}
      {/* ── Phần lối tắt quản trị ──────────────────────────────────────── */}
      <SectionCard title="Lối tắt quản trị" icon={Gauge}>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {/* Lối tắt đến trang vận hành hệ thống */}
          <Link
            href="/ops"
            className="group flex items-center gap-3 rounded-card border border-line bg-surface p-4 shadow-card transition hover:border-brand-300 hover:bg-brand-50"
          >
            <span className="rounded-control bg-brand-50 p-2 text-brand-600">
              <Gauge size={18} />
            </span>
            <div>
              <p className="text-sm font-medium text-ink">Vận hành hệ thống</p>
              <p className="text-xs text-ink-muted">Ops Center</p>
            </div>
          </Link>
          {/* Lối tắt đến trang cài đặt tài khoản */}
          <Link
            href="/settings"
            className="group flex items-center gap-3 rounded-card border border-line bg-surface p-4 shadow-card transition hover:border-brand-300 hover:bg-brand-50"
          >
            <span className="rounded-control bg-brand-50 p-2 text-brand-600">
              <Settings size={18} />
            </span>
            <div>
              <p className="text-sm font-medium text-ink">Cài đặt tài khoản</p>
              <p className="text-xs text-ink-muted">Nhân viên & login</p>
            </div>
          </Link>
          {/* Lối tắt đến trang lịch sử thao tác */}
          <Link
            href="/audit-log"
            className="group flex items-center gap-3 rounded-card border border-line bg-surface p-4 shadow-card transition hover:border-brand-300 hover:bg-brand-50"
          >
            <span className="rounded-control bg-brand-50 p-2 text-brand-600">
              <ScrollText size={18} />
            </span>
            <div>
              <p className="text-sm font-medium text-ink">Lịch sử thao tác</p>
              <p className="text-xs text-ink-muted">Audit log</p>
            </div>
          </Link>
          {/* Lối tắt đến trang báo cáo */}
          <Link
            href="/reports"
            className="group flex items-center gap-3 rounded-card border border-line bg-surface p-4 shadow-card transition hover:border-brand-300 hover:bg-brand-50"
          >
            <span className="rounded-control bg-brand-50 p-2 text-brand-600">
              <BarChart3 size={18} />
            </span>
            <div>
              <p className="text-sm font-medium text-ink">Báo cáo</p>
              <p className="text-xs text-ink-muted">Số liệu vận hành</p>
            </div>
          </Link>
        </div>
      </SectionCard>
    </main>
  );
}