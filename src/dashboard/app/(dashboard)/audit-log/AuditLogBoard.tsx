"use client";

// Nhập các hook useMemo và useState từ React để quản lý state và tối ưu hiệu năng
import { useMemo, useState } from "react";
// Nhập các component StatCard và StatRow để hiển thị thẻ thống kê
import StatCard, { StatRow } from "@/components/ui/StatCard";
// Nhập các icon từ thư viện lucide-react
import { Activity, Users, Calendar, AlertCircle, Copy, ExternalLink, Search } from "lucide-react";
// Nhập các hàm định dạng thời gian và ngày
import { fmtTime, fmtDate } from "../../../lib/datetime";
// Nhập kiểu dữ liệu AuditEvent từ file types
import type { AuditEvent } from "./types";

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

/** Extract before/after diff from event payload */
/** Trích xuất sự khác biệt trước/sau từ payload của sự kiện */
function extractChanges(
  payload: Record<string, unknown> | null, // Payload của sự kiện, có thể null
): { field: string; before: string; after: string }[] {
  // Nếu payload rỗng thì trả về mảng rỗng
  if (!payload) return [];
  // Khởi tạo mảng chứa các thay đổi
  const changes: { field: string; before: string; after: string }[] = [];

  // Nếu payload có trường changes và là object
  if (payload.changes && typeof payload.changes === "object") {
    // Ép kiểu changes thành object chứa các cặp old/new
    const ch = payload.changes as Record<
      string,
      { old?: unknown; new?: unknown }
    >;
    // Lặp qua từng trường trong changes
    for (const [field, val] of Object.entries(ch)) {
      // Thêm thay đổi vào mảng: tên trường, giá trị cũ, giá trị mới
      changes.push({
        field, // Tên trường dữ liệu
        before: val?.old != null ? String(val.old) : "—", // Giá trị cũ hoặc dấu gạch ngang
        after: val?.new != null ? String(val.new) : "—", // Giá trị mới hoặc dấu gạch ngang
      });
    }
  } else if (payload.before && payload.after) {
    // Nếu payload có trường before và after (dạng so sánh trước/sau)
    const before = payload.before as Record<string, unknown>; // Ép kiểu before thành object
    const after = payload.after as Record<string, unknown>; // Ép kiểu after thành object
    // Tạo tập hợp tất cả các key từ cả before và after
    const allKeys = new Set([...Object.keys(before), ...Object.keys(after)]);
    // Lặp qua từng key
    for (const key of allKeys) {
      const b = before[key]; // Giá trị trước
      const a = after[key]; // Giá trị sau
      // Nếu giá trị trước và sau khác nhau (so sánh JSON)
      if (JSON.stringify(b) !== JSON.stringify(a)) {
        // Thêm thay đổi vào mảng
        changes.push({
          field: key, // Tên trường
          before: b != null ? String(b) : "—", // Giá trị cũ hoặc dấu gạch ngang
          after: a != null ? String(a) : "—", // Giá trị mới hoặc dấu gạch ngang
        });
      }
    }
  } else {
    // Trường hợp payload không có changes hoặc before/after
    // Tạo tập hợp các trường cần bỏ qua (thông tin nhân sự không cần hiển thị)
    const skip = new Set(["staff_name", "staff_id", "patient_name", "patient_id"]);
    // Lặp qua từng trường trong payload
    for (const [key, val] of Object.entries(payload)) {
      // Bỏ qua nếu trường nằm trong danh sách skip hoặc giá trị null
      if (skip.has(key) || val == null) continue;
      // Bỏ qua nếu giá trị là object (quá phức tạp để hiển thị)
      if (typeof val === "object") continue;
      // Thêm thay đổi vào mảng: chỉ có giá trị mới, không có giá trị cũ
      changes.push({ field: key, before: "—", after: String(val) });
    }
  }
  // Giới hạn tối đa 10 thay đổi để tránh hiển thị quá nhiều
  return changes.slice(0, 10);
}

// Bảng nhãn tiếng Việt cho các tên trường dữ liệu
const FIELD_LABELS: Record<string, string> = {
  status: "Trạng thái", // Trạng thái
  slot_start: "Khung giờ", // Khung giờ bắt đầu
  doctor_id: "Bác sĩ", // ID bác sĩ
  service_type_id: "Dịch vụ", // ID loại dịch vụ
  full_name: "Họ tên", // Họ tên đầy đủ
  phone_primary: "SĐT", // Số điện thoại chính
  booking_channel: "Kênh đặt", // Kênh đặt lịch
  location_id: "Cơ sở", // ID cơ sở
  step: "Bước", // Bước trong quy trình
  category: "Loại", // Loại
  description: "Mô tả", // Mô tả
};

// Component chính AuditLogBoard — hiển thị bảng lịch sử thao tác
export default function AuditLogBoard({ events, soNguoi }: Props) {
  // State lưu từ khóa tìm kiếm
  const [search, setSearch] = useState("");
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
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase(); // Chuẩn hóa từ khóa tìm kiếm
    return events.filter((e) => {
      // Nếu tab không phải "all" và loại đối tượng không khớp tab thì loại bỏ
      if (tab !== "all" && aggregateToTab(e.aggregate_type) !== tab) return false;
      // Nếu không có từ khóa tìm kiếm thì giữ lại tất cả
      if (!q) return true;
      // Tìm kiếm trong nhiều trường: loại sự kiện, loại đối tượng, nguồn thao tác, tên người thao tác, nhãn đối tượng, nhãn hành động, payload
      return (
        e.event_type.toLowerCase().includes(q) || // Tìm trong loại sự kiện
        e.aggregate_type.toLowerCase().includes(q) || // Tìm trong loại đối tượng
        (e.nguon_thao_tac ?? "").toLowerCase().includes(q) || // Tìm trong nguồn thao tác
        (e.actor_name ?? "").toLowerCase().includes(q) || // Tìm trong tên người thao tác
        e.subject_label.toLowerCase().includes(q) || // Tìm trong nhãn đối tượng
        e.action_label.toLowerCase().includes(q) || // Tìm trong nhãn hành động
        JSON.stringify(e.payload ?? {}).toLowerCase().includes(q) // Tìm trong payload
      );
    });
  }, [events, search, tab]); // Chỉ tính lại khi events, search hoặc tab thay đổi

  // Trích xuất các thay đổi dữ liệu từ payload của sự kiện được chọn
  const changes = sel ? extractChanges(sel.payload) : [];

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
                  <th className="px-4 py-2.5 font-medium">Đối tượng</th> {/* Cột đối tượng */}
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
                <span className="inline-block rounded-full bg-brand-50 px-2 py-0.5 text-[10px] font-medium text-brand-700">
                  {/* Hiển thị tên loại đối tượng theo tiếng Việt */}
                  {sel.aggregate_type === "appointment" ? "Lịch hẹn" : sel.aggregate_type === "patient" ? "Khách hàng" : sel.aggregate_type}
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
              {/* Đối tượng bị ảnh hưởng */}
              <div className="flex justify-between">
                <dt className="text-ink-muted">Đối tượng</dt>
                <dd className="font-mono text-ink">{sel.subject_label}</dd>
              </div>
              {/* Nguồn thao tác */}
              <div className="flex justify-between">
                <dt className="text-ink-muted">Nguồn thao tác</dt>
                <dd className="text-ink">{sel.nguon_thao_tac ?? "—"}</dd>
              </div>
            </dl>

            {/* Phần hiển thị dữ liệu thay đổi */}
            <div className="space-y-1.5 border-t border-line pt-3">
              {/* Tiêu đề phần dữ liệu thay đổi */}
              <h4 className="text-xs font-semibold text-ink">Dữ liệu thay đổi</h4>
              {/* Nếu có thay đổi */}
              {changes.length > 0 ? (
                // Bảng hiển thị các thay đổi
                <div className="rounded-xl border border-line overflow-hidden text-xs">
                  <table className="w-full text-left">
                    {/* Tiêu đề bảng */}
                    <thead className="bg-surface-muted text-ink-muted border-b border-line text-[11px]">
                      <tr>
                        <th className="p-2">Trường dữ liệu</th> {/* Cột tên trường */}
                        <th className="p-2">Trước</th> {/* Cột giá trị trước */}
                        <th className="p-2">Sau</th> {/* Cột giá trị sau */}
                      </tr>
                    </thead>
                    {/* Thân bảng */}
                    <tbody className="divide-y divide-line text-[11px]">
                      {/* Lặp qua từng thay đổi */}
                      {changes.map((c, i) => (
                        <tr key={i}>
                          {/* Tên trường (dùng nhãn tiếng Việt nếu có) */}
                          <td className="p-2 text-ink-muted">{FIELD_LABELS[c.field] ?? c.field}</td>
                          {/* Giá trị trước (màu vàng) */}
                          <td className="p-2 text-amber-600">{c.before}</td>
                          {/* Giá trị sau (màu xanh) */}
                          <td className="p-2 font-medium text-success">{c.after}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                // Nếu không có thay đổi thì hiển thị thông báo
                <p className="text-xs text-ink-muted rounded-xl border border-dashed border-line p-3">
                  Không có dữ liệu thay đổi chi tiết cho sự kiện này.
                </p>
              )}
            </div>

            {/* Phần ngữ cảnh (nếu có) */}
            {sel.payload?.context ? (
              <div className="rounded-xl border border-line p-3 text-xs">
                <h4 className="font-semibold text-ink mb-1">Ngữ cảnh</h4>
                <p className="text-ink-soft">{String(sel.payload.context)}</p>
              </div>
            ) : null}

            {/* Các nút hành động: sao chép mã và xem sự kiện liên quan */}
            <div className="flex items-center gap-2 pt-2 border-t border-line">
              {/* Nút sao chép mã sự kiện */}
              <button
                type="button"
                onClick={() => navigator.clipboard?.writeText(sel.id)} // Sao chép ID vào clipboard
                className="flex-1 inline-flex items-center justify-center gap-1 rounded-xl border border-line bg-surface py-2 text-xs font-medium text-ink-soft hover:bg-surface-muted"
              >
                <Copy size={13} /> Sao chép mã sự kiện
              </button>
              {/* Nút xem sự kiện liên quan (chưa có chức năng) */}
              <button
                type="button"
                className="flex-1 inline-flex items-center justify-center gap-1 rounded-xl bg-brand-600 py-2 text-xs font-medium text-white shadow-sm hover:bg-brand-700"
              >
                <ExternalLink size={13} /> Xem sự kiện liên quan
              </button>
            </div>
          </aside>
        ) : null}
      </div>
    </div>
  );
}