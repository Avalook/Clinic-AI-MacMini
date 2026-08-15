"use client";

// Nhập các hook useMemo và useState từ React để quản lý state và tối ưu hiệu năng
import { useMemo, useState } from "react";
// Nhập các component StatCard và StatRow để hiển thị thẻ thống kê
import StatCard, { StatRow } from "@/components/ui/StatCard";
// Nhập các icon từ thư viện lucide-react
import { Activity, Users, Calendar, AlertCircle, Search } from "lucide-react";
// Nhập các hàm định dạng thời gian và ngày
import { fmtTime, fmtDate } from "../../../lib/datetime";
// Nhập kiểu dữ liệu AuditEvent từ file types
import type { AuditEvent } from "./types";
import { ALL_ROLES, ROLE_LABEL, type ClinicRole } from "../../../lib/roles";

// Định nghĩa interface cho props (dữ liệu truyền vào component)
interface Props {
  events: AuditEvent[]; // Danh sách các sự kiện audit
  /** Số NGƯỜI đã thao tác, do backend đếm theo actor_staff_id. Trước đây màn
   *  này tự đếm `new Set(source)` nên ra 14 — đó là 14 tên đường ghi. */
  soNguoi: number; // Số người đã thao tác (backend đếm theo actor_staff_id)
}

// Định nghĩa kiểu tab lọc: tất cả, khách hàng, lịch hẹn, công việc, hệ thống
type AuditTab = "all" | "patient" | "appointment" | "task" | "system";

// Định nghĩa danh sách các tab lọc với key và nhãn hiển thị
const TABS: { key: AuditTab; label: string }[] = [
  { key: "all", label: "Tất cả" }, // Tab hiển thị tất cả sự kiện
  { key: "patient", label: "Khách hàng" }, // Tab lọc theo khách hàng
  { key: "appointment", label: "Lịch hẹn" }, // Tab lọc theo lịch hẹn
  { key: "task", label: "Công việc" }, // Tab lọc theo công việc
  { key: "system", label: "Hệ thống" }, // Tab lọc theo hệ thống
];

// Hàm chuyển đổi aggregate_type (loại đối tượng) sang tab tương ứng
function aggregateToTab(agg: string): AuditTab {
  // Nếu là patient hoặc clinic_patient thì thuộc tab khách hàng
  if (agg === "patient" || agg === "clinic_patient") return "patient";
  // Nếu là appointment thì thuộc tab lịch hẹn
  if (agg === "appointment") return "appointment";
  // work_item = một bước trong quy trình khám (workflow kernel). Nó là "công
  // việc" theo đúng nghĩa tab này, chứ không phải "hệ thống".
  // Nếu là cskh_action, staff_task hoặc work_item thì thuộc tab công việc
  if (agg === "cskh_action" || agg === "staff_task" || agg === "work_item")
    return "task";
  // Mặc định thuộc tab hệ thống
  return "system";
}

// KHỐI "DỮ LIỆU THAY ĐỔI" ĐÃ BỎ (Quang chốt 09/08/2026).
//
// Nó hiện ra một bảng vô nghĩa: "0 → {", "1 → \"", "2 → s"… — tức là đang lặp
// qua TỪNG KÝ TỰ của một chuỗi. Lý do: `event_log.payload` là jsonb, asyncpg
// trả jsonb về dưới dạng CHUỖI (dự án không đăng ký type codec), nên trường
// `payload` đi tới đây là một chuỗi JSON chứ không phải object —
// `Object.entries("{\"slot_...\"}")` cho ra cặp chỉ-số → ký-tự.
//
// Đã sửa cả hai đầu: backend nay parse chuỗi ấy trước khi trả về
// (audit_log_service.py), và khối bảng này bỏ hẳn — nó bày ra tên cột thô của
// database cho người trực đọc, đúng thứ Quang gọi là "lộ code". Hai nút
// "Sao chép mã sự kiện" / "Xem sự kiện liên quan" đi cùng: nút thứ hai chưa
// bao giờ có onClick.

// HAI BẢNG NHÃN TỪNG NẰM Ở ĐÂY ĐÃ CHUYỂN VỀ `services/audit_labels.py`.
//
// `NHAN_NGUON` có 7 mục cho một từ vựng hơn 30 đường ghi, `NHAN_LOAI` có 12 mục
// cho 24 loại đối tượng — nên phần lớn dòng rơi xuống nhánh `?? nguon` và in ra
// địa chỉ mã nguồn: ô "Làm ở màn" hiện "api:booking-override", cái chip hiện
// "roster_week". Đúng cái bệnh mà bảng nhãn sự kiện đã chữa một lần rồi, tái
// phát ở hai cột bên cạnh vì chúng ở lại trong TSX.
//
// Nay backend trả sẵn `nguon_label` và `aggregate_label`, và bài kiểm chống
// lệch canh cả bốn từ vựng cùng một chỗ.

// Component chính AuditLogBoard — hiển thị bảng lịch sử thao tác
export default function AuditLogBoard({ events, soNguoi }: Props) {
  // State lưu từ khóa tìm kiếm
  const [search, setSearch] = useState("");
  const [vaiLoc, setVaiLoc] = useState<string>("all");
  // State lưu tab đang chọn (mặc định là "all" - tất cả)
  const [tab, setTab] = useState<AuditTab>("all");
  // State lưu ID sự kiện đang được chọn (mặc định là sự kiện đầu tiên)
  const [selId, setSelId] = useState<string | null>(events[0]?.id ?? null);

  // Tìm sự kiện được chọn theo ID, nếu không tìm thấy thì dùng sự kiện đầu tiên
  const sel = events.find((e) => e.id === selId) ?? events[0] ?? null;

  // Số NGƯỜI, backend đếm theo actor_staff_id. Không phải số nguồn máy —
  // cách đếm cũ (`new Set(source)`) cho ra 14, tức 14 tên đường ghi.
  // Số người thao tác duy nhất (do backend đếm)
  const uniqueSources = soNguoi;
  // Đếm số sự kiện liên quan đến lịch hẹn (dùng useMemo để tối ưu hiệu năng)
  const apptEvents = useMemo(
    () => events.filter((e) => e.aggregate_type === "appointment").length,
    [events], // Chỉ tính lại khi events thay đổi
  );
  // Đếm số sự kiện cảnh báo (từ chối, hủy, lỗi) — dùng useMemo để tối ưu
  const alertEvents = useMemo(
    () =>
      events.filter(
        (e) =>
          e.event_type.includes("declined") || // Sự kiện bị từ chối
          e.event_type.includes("cancelled") || // Sự kiện bị hủy
          e.event_type.includes("error"), // Sự kiện lỗi
      ).length,
    [events], // Chỉ tính lại khi events thay đổi
  );

  // Lọc danh sách sự kiện theo tab và từ khóa tìm kiếm (dùng useMemo để tối ưu)
  // ĐẾM THEO VAI, tính trên toàn bộ sự kiện (không phụ thuộc tab/tìm kiếm) để
  // con số trong ô chọn không nhảy theo thao tác khác.
  const soTheoVai = useMemo(() => {
    const m = new Map<string, number>();
    for (const e of events) {
      const v = e.actor_role ?? "HE_THONG";
      m.set(v, (m.get(v) ?? 0) + 1);
    }
    return m;
  }, [events]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase(); // Chuẩn hóa từ khóa tìm kiếm
    return events.filter((e) => {
      // Nếu tab không phải "all" và loại đối tượng không khớp tab thì loại bỏ
      if (tab !== "all" && aggregateToTab(e.aggregate_type) !== tab) return false;
      // Lọc theo VAI của người thao tác. "Ai đã làm việc này" là câu hỏi đầu
      // tiên của mọi lần tra nhật ký, và trước đây màn này không trả lời được:
      // `actor_role` vẫn về cùng dữ liệu nhưng không màn nào dùng tới.
      if (vaiLoc !== "all") {
        const v = e.actor_role ?? "HE_THONG";
        if (v !== vaiLoc) return false;
      }
      // Nếu không có từ khóa tìm kiếm thì giữ lại tất cả
      if (!q) return true;
      // Tìm kiếm trong nhiều trường: loại sự kiện, loại đối tượng, nguồn thao tác, tên người thao tác, nhãn đối tượng, nhãn hành động, payload
      return (
        e.event_type.toLowerCase().includes(q) || // Tìm trong loại sự kiện
        e.aggregate_type.toLowerCase().includes(q) || // Tìm trong loại đối tượng
        (e.nguon_thao_tac ?? "").toLowerCase().includes(q) || // Tìm trong nguồn thao tác
        e.nguon_label.toLowerCase().includes(q) || // …và trong tên màn tiếng Việt
        e.aggregate_label.toLowerCase().includes(q) || // Tìm trong loại đối tượng
        (e.actor_name ?? "").toLowerCase().includes(q) || // Tìm trong tên người thao tác
        e.subject_label.toLowerCase().includes(q) || // Tìm trong nhãn đối tượng
        e.action_label.toLowerCase().includes(q) || // Tìm trong nhãn hành động
        JSON.stringify(e.payload ?? {}).toLowerCase().includes(q) // Tìm trong payload
      );
    });
  }, [events, search, tab, vaiLoc]); // Tính lại khi một trong bốn thứ đổi

  return (
    // Container chính với khoảng cách dọc giữa các phần
    <div className="space-y-4">
      {/* Hàng thống kê: 4 thẻ hiển thị số liệu tổng quan */}
      <StatRow>
        {/* Thẻ: tổng số sự kiện hôm nay */}
        <StatCard label="Sự kiện hôm nay" value={events.length} tone="brand" icon={<Activity className="size-5" />} />
        {/* Thẻ: số người dùng hoạt động */}
        <StatCard label="Người dùng hoạt động" value={uniqueSources} tone="success" icon={<Users className="size-5 text-success" />} />
        {/* Thẻ: số thay đổi lịch hẹn */}
        <StatCard label="Thay đổi lịch hẹn" value={apptEvents} tone="warning" icon={<Calendar className="size-5 text-warning" />} />
        {/* Thẻ: số cảnh báo cần xem */}
        <StatCard label="Cảnh báo cần xem" value={alertEvents} tone="danger" icon={<AlertCircle className="size-5 text-danger" />} />
      </StatRow>

      {/* Tabs */}
      {/* Thanh tab lọc: Tất cả, Khách hàng, Lịch hẹn, Công việc, Hệ thống */}
      <div className="flex overflow-x-auto border-b border-line text-sm">
        {/* Lặp qua từng tab */}
        {TABS.map((t) => (
          <button
            key={t.key} // Key duy nhất cho mỗi tab
            type="button" // Loại nút là button
            onClick={() => setTab(t.key)} // Khi click thì đổi tab đang chọn
            className={`shrink-0 border-b-2 px-3 py-2.5 font-medium transition-colors ${
              // Nếu tab đang được chọn thì highlight màu brand
              tab === t.key
                ? "border-brand-600 text-brand-700"
                : "border-transparent text-ink-muted hover:text-ink" // Ngược lại thì màu mờ
            }`}
          >
            {t.label} {/* Nhãn của tab */}
          </button>
        ))}
      </div>

      {/* Thanh tìm kiếm và nút xuất CSV */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line bg-surface p-3 shadow-card">
        {/* Ô tìm kiếm */}
        <label className="flex min-h-9 min-w-[280px] flex-1 items-center gap-2 rounded-xl border border-line bg-surface px-3 text-ink-muted focus-within:border-brand-500 lg:max-w-md">
          {/* Icon tìm kiếm */}
          <Search className="size-4" aria-hidden="true" />
          {/* Input tìm kiếm */}
          <input
            value={search} // Giá trị từ state search
            onChange={(e) => setSearch(e.target.value)} // Cập nhật state khi gõ
            placeholder="Tìm theo khách hàng, mã sự kiện hoặc nội dung..." // Gợi ý tìm kiếm
            className="min-w-0 flex-1 bg-transparent text-xs text-ink outline-none placeholder:text-ink-faint"
          />
        </label>
        {/* Lọc theo VAI của người thao tác — đủ MỌI vai của phòng khám, kèm
            số sự kiện của từng vai để thấy ngay vai nào trống. */}
        <label className="flex min-h-9 items-center gap-2 rounded-xl border border-line bg-surface px-3 text-xs text-ink-muted focus-within:border-brand-500">
          <span className="shrink-0">Vai trò</span>
          <select
            value={vaiLoc}
            onChange={(e) => setVaiLoc(e.target.value)}
            className="min-w-[150px] bg-transparent py-1.5 text-xs font-medium text-ink outline-none"
          >
            <option value="all">Tất cả ({events.length})</option>
            {ALL_ROLES.map((r: ClinicRole) => (
              <option key={r} value={r}>
                {ROLE_LABEL[r]} ({soTheoVai.get(r) ?? 0})
              </option>
            ))}
            {/* Sự kiện do chính hệ thống sinh ra (không có người thao tác) —
                phải lọc được, vì đó là nhóm hay bị bỏ sót nhất khi truy vết. */}
            <option value="HE_THONG">
              Hệ thống ({soTheoVai.get("HE_THONG") ?? 0})
            </option>
          </select>
        </label>

        {/* Nút xuất CSV (chưa có chức năng) */}
        <button
          type="button"
          className="rounded-xl border border-line bg-surface px-3 py-2 text-xs font-medium text-ink-soft hover:bg-surface-muted"
        >
          ⬇ Xuất CSV
        </button>
      </div>

      {/* Lưới 2 cột: danh sách sự kiện (trái) + chi tiết sự kiện (phải) */}
      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(360px,420px)]">
        {/* Cột trái: bảng danh sách sự kiện */}
        <div className="min-w-0 overflow-hidden rounded-2xl border border-line bg-surface shadow-card">
          {/* Tiêu đề bảng */}
          <header className="border-b border-line px-4 py-3">
            <h2 className="text-sm font-semibold text-ink">
              {filtered.length} sự kiện · Sắp xếp mới nhất {/* Số sự kiện sau khi lọc */}
            </h2>
          </header>
          {/* Vùng cuộn dọc cho bảng */}
          <div className="max-h-[560px] overflow-y-auto">
            {/* Bảng danh sách sự kiện */}
            <table className="w-full text-left text-xs">
              {/* Tiêu đề cột, cố định khi cuộn */}
              <thead className="sticky top-0 bg-surface-muted text-ink-muted border-b border-line">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Thời gian</th> {/* Cột thời gian */}
                  <th className="px-4 py-2.5 font-medium">Người thực hiện</th> {/* Cột người thực hiện */}
                  <th className="px-4 py-2.5 font-medium">Khách hàng</th> {/* Việc này về ai */}
                  <th className="px-4 py-2.5 font-medium">Hành động</th> {/* Cột hành động */}
                </tr>
              </thead>
              {/* Thân bảng với đường kẻ phân cách */}
              <tbody className="divide-y divide-line">
                {/* Lặp qua danh sách sự kiện đã lọc */}
                {filtered.map((e) => {
                  // Kiểm tra xem sự kiện này có đang được chọn không
                  const active = sel?.id === e.id;
                  return (
                    // Mỗi dòng là một sự kiện
                    <tr
                      key={e.id} // Key duy nhất
                      onClick={() => setSelId(e.id)} // Click để chọn sự kiện
                      className={`cursor-pointer transition-colors ${active ? "bg-brand-50" : "hover:bg-surface-muted"}`} // Highlight nếu đang chọn
                    >
                      {/* Cột thời gian */}
                      <td className="px-4 py-3 font-mono text-ink-muted">{fmtTime(e.occurred_at)}</td>
                      {/* Cột người thực hiện */}
                      <td className="px-4 py-3 font-medium text-ink">{e.actor_name ?? "Hệ thống"}</td>
                      {/* Cột đối tượng */}
                      <td className="px-4 py-3 text-ink-soft">{e.subject_label}</td>
                      {/* Cột hành động */}
                      <td className="px-4 py-3"><span className="font-medium text-brand-700">{e.action_label}</span></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Cột phải: chi tiết sự kiện được chọn */}
        {sel ? (
          <aside className="w-full shrink-0 space-y-4 rounded-2xl border border-line bg-surface p-4 shadow-card">
            {/* Phần đầu chi tiết: loại đối tượng + tên hành động + mã sự kiện */}
            <div className="flex items-start justify-between border-b border-line pb-3">
              <div>
                {/* Badge loại đối tượng */}
                <span className="inline-block rounded-full bg-brand-50 px-2 py-0.5 text-label font-medium text-brand-700">
                  {sel.aggregate_label}
                </span>
                {/* Tên hành động */}
                <h3 className="mt-1 text-base font-semibold text-ink">{sel.action_label}</h3>
                {/* Mã sự kiện (12 ký tự đầu của ID) */}
                <p className="text-xs font-mono text-ink-muted">EV-{sel.id.slice(0, 12)}</p>
              </div>
            </div>

            {/* Danh sách thông tin chi tiết */}
            <dl className="space-y-2 text-xs">
              {/* Người thực hiện */}
              <div className="flex justify-between">
                <dt className="text-ink-muted">Người thực hiện</dt>
                <dd className="font-medium text-ink">{sel.actor_name ?? "Hệ thống"}</dd>
              </div>
              {/* Thời gian xảy ra */}
              <div className="flex justify-between">
                <dt className="text-ink-muted">Thời gian</dt>
                <dd className="font-mono text-ink">{fmtTime(sel.occurred_at)} · {fmtDate(sel.occurred_at)}</dd>
              </div>
              {/* Việc này về ai */}
              <div className="flex justify-between gap-3">
                <dt className="shrink-0 text-ink-muted">Khách hàng</dt>
                <dd className="text-right font-medium text-ink">{sel.subject_label}</dd>
              </div>
              {/* Thao tác đi vào từ màn nào */}
              <div className="flex justify-between gap-3">
                <dt className="shrink-0 text-ink-muted">Làm ở màn</dt>
                <dd className="text-right text-ink">{sel.nguon_label}</dd>
              </div>
            </dl>

            {/* Ngữ cảnh do chính đường ghi đặt vào — câu tiếng Việt, không phải
                tên cột database. Chỉ hiện khi có. */}
            {sel.payload?.context ? (
              <div className="rounded-xl border border-line p-3 text-xs">
                <h4 className="mb-1 font-semibold text-ink">Ngữ cảnh</h4>
                <p className="text-ink-soft">{String(sel.payload.context)}</p>
              </div>
            ) : null}
          </aside>
        ) : null}
      </div>
    </div>
  );
}