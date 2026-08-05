"use client";

// ResultReviewBoard — Duyệt kết quả (image_9 + image_3).
// Hàng đợi kết quả XN chờ bác sĩ duyệt. Ký duyệt / trả lại chỉnh sửa.

// Nhập các hook useMemo và useState từ React để quản lý state và tối ưu hiệu năng
import { useMemo, useState } from "react";
// Nhập hằng số VN_TZ (múi giờ Việt Nam) từ file datetime
import { VN_TZ } from "../../../lib/datetime";

// Định nghĩa interface cho thông tin bệnh nhân trong kết quả xét nghiệm
interface ReviewPatient {
  full_name: string | null; // Tên đầy đủ của bệnh nhân, có thể null
  phone_primary: string | null; // Số điện thoại chính, có thể null
}

// Định nghĩa interface cho một dòng kết quả xét nghiệm cần duyệt
interface ReviewRow {
  lab_result_id: string; // ID của kết quả xét nghiệm
  test_code: string; // Mã xét nghiệm
  test_name: string; // Tên xét nghiệm
  result_value: string | null; // Giá trị kết quả dạng chuỗi, có thể null
  result_numeric: number | null; // Giá trị kết quả dạng số, có thể null
  result_unit: string | null; // Đơn vị đo, có thể null
  reference_range_low: number | null; // Giới hạn dưới của khoảng tham chiếu, có thể null
  reference_range_high: number | null; // Giới hạn trên của khoảng tham chiếu, có thể null
  flag: string | null; // Cờ đánh dấu (NORMAL, HIGH, LOW...), có thể null
  triage_group: string | null; // Nhóm phân loại ưu tiên, có thể null
  requires_doctor_review: boolean; // Có cần bác sĩ duyệt không
  is_finalized: boolean; // Đã được chốt kết quả chưa
  result_received_at: string; // Thời gian nhận kết quả
  patient: ReviewPatient | null; // Thông tin bệnh nhân, có thể null
}

// Định nghĩa interface cho props (dữ liệu truyền vào component)
interface Props {
  results: ReviewRow[]; // Danh sách kết quả xét nghiệm cần duyệt
}

// Hàm định dạng ngày giờ theo múi giờ Việt Nam
const fmtDate = (iso: string) =>
  new Date(iso).toLocaleString("vi-VN", { timeZone: VN_TZ });

// Bảng nhãn tiếng Việt cho các cờ đánh dấu kết quả
const FLAG_LABEL: Record<string, string> = {
  NORMAL: "Bình thường", // Kết quả bình thường
  HIGH: "Cao", // Kết quả cao
  LOW: "Thấp", // Kết quả thấp
  CRITICAL_HIGH: "Cao nguy kịch", // Kết quả cao nguy kịch
  CRITICAL_LOW: "Thấp nguy kịch", // Kết quả thấp nguy kịch
  ABNORMAL: "Bất thường", // Kết quả bất thường
};

// Component chính ResultReviewBoard — hiển thị bảng duyệt kết quả xét nghiệm
export default function ResultReviewBoard({ results }: Props) {
  // State lưu ID của kết quả đang được chọn
  const [selectedId, setSelectedId] = useState<string | null>(null);
  // State lưu từ khóa tìm kiếm
  const [search, setSearch] = useState("");

  // Tìm kết quả được chọn theo ID (dùng useMemo để tối ưu hiệu năng)
  const selected = useMemo(
    () => results.find((r) => r.lab_result_id === selectedId) ?? null,
    [results, selectedId], // Chỉ tính lại khi results hoặc selectedId thay đổi
  );

  // Lọc danh sách kết quả theo từ khóa tìm kiếm (dùng useMemo để tối ưu)
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase(); // Chuẩn hóa từ khóa tìm kiếm
    if (!q) return results; // Nếu không có từ khóa thì trả về toàn bộ
    return results.filter(
      (r) =>
        r.patient?.full_name?.toLowerCase().includes(q) || // Tìm theo tên bệnh nhân
        r.test_name.toLowerCase().includes(q) || // Tìm theo tên xét nghiệm
        r.test_code.toLowerCase().includes(q), // Tìm theo mã xét nghiệm
    );
  }, [results, search]); // Chỉ tính lại khi results hoặc search thay đổi

  return (
    // Lưới 2 cột: danh sách chờ duyệt (trái) + chi tiết (phải)
    <div className="grid h-full grid-cols-[minmax(320px,400px)_1fr] gap-4 p-4">
      {/* Cột trái: hàng đợi */}
      {/* Phần danh sách các kết quả chờ duyệt */}
      <section className="flex flex-col rounded-control border border-line bg-surface">
        {/* Phần đầu: tiêu đề + ô tìm kiếm */}
        <div className="border-b border-line p-3">
          {/* Tiêu đề */}
          <h2 className="text-sm font-semibold text-ink">Chờ duyệt</h2>
          {/* Số lượng kết quả */}
          <p className="mt-0.5 text-xs text-ink-muted">
            {results.length} kết quả · {filtered.length} hiển thị
          </p>
          {/* Ô tìm kiếm */}
          <input
            value={search} // Giá trị từ state search
            onChange={(e) => setSearch(e.target.value)} // Cập nhật state khi gõ
            placeholder="Tìm BN / xét nghiệm…" // Gợi ý tìm kiếm
            className="mt-2 w-full rounded-control border border-line bg-surface-muted px-2.5 py-1.5 text-sm text-ink outline-none focus:border-brand-500"
          />
        </div>
        {/* Vùng cuộn danh sách */}
        <div className="flex-1 overflow-y-auto">
          {/* Nếu không có kết quả nào */}
          {filtered.length === 0 ? (
            // Hiển thị thông báo trống
            <p className="p-4 text-sm text-ink-muted">Không có kết quả chờ duyệt.</p>
          ) : (
            // Lặp qua từng kết quả đã lọc
            filtered.map((r) => (
              // Mỗi kết quả là một nút có thể click
              <button
                key={r.lab_result_id} // Key duy nhất
                onClick={() => setSelectedId(r.lab_result_id)} // Click để chọn kết quả
                className={`block w-full border-b border-line px-3 py-2.5 text-left transition-colors hover:bg-surface-muted ${
                  // Highlight nếu đang được chọn
                  selectedId === r.lab_result_id ? "bg-surface-selected" : ""
                }`}
              >
                {/* Dòng 1: tên bệnh nhân + cờ đánh dấu */}
                <div className="flex items-center justify-between gap-2">
                  {/* Tên bệnh nhân */}
                  <span className="text-sm font-medium text-ink">
                    {r.patient?.full_name ?? "Chưa có tên"}
                  </span>
                  {/* Badge cờ đánh dấu với màu theo mức độ */}
                  <span
                    className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${
                      // Nếu là nguy kịch thì màu đỏ
                      r.flag === "CRITICAL_HIGH" || r.flag === "CRITICAL_LOW"
                        ? "bg-danger-bg text-danger"
                        : // Nếu là bất thường (không phải NORMAL) thì màu vàng
                          r.flag && r.flag !== "NORMAL"
                          ? "bg-warning-bg text-warning"
                          : // Bình thường thì màu xanh
                            "bg-success-bg text-success"
                    }`}
                  >
                    {/* Nhãn cờ đánh dấu */}
                    {FLAG_LABEL[r.flag ?? ""] ?? r.flag ?? "—"}
                  </span>
                </div>
                {/* Dòng 2: tên xét nghiệm + giá trị kết quả + đơn vị */}
                <div className="mt-0.5 truncate text-xs text-ink-muted">
                  {r.test_name} · {r.result_value ?? r.result_numeric ?? "—"}
                  {r.result_unit ? ` ${r.result_unit}` : ""}
                </div>
                {/* Dòng 3: thời gian nhận kết quả */}
                <div className="mt-0.5 text-xs text-ink-faint">
                  {fmtDate(r.result_received_at)}
                </div>
              </button>
            ))
          )}
        </div>
      </section>

      {/* Cột phải: chi tiết + hành động */}
      {/* Phần hiển thị chi tiết kết quả được chọn và các nút hành động */}
      <section className="overflow-y-auto">
        {/* Nếu có kết quả được chọn */}
        {selected ? (
          <div className="rounded-control border border-line bg-surface p-4">
            {/* Phần đầu: tên bệnh nhân + mã xét nghiệm + nhóm phân loại */}
            <div className="flex items-start justify-between gap-3">
              <div>
                {/* Tên bệnh nhân */}
                <h3 className="text-base font-semibold text-ink">
                  {selected.patient?.full_name ?? "Chưa có tên"}
                </h3>
                {/* Số điện thoại + mã xét nghiệm */}
                <p className="mt-0.5 text-xs text-ink-muted">
                  {selected.patient?.phone_primary ?? "—"} · {selected.test_code}
                </p>
              </div>
              {/* Badge nhóm phân loại ưu tiên */}
              <span className="rounded-full bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700">
                {selected.triage_group ?? "PENDING"}
              </span>
            </div>

            {/* Phần hiển thị chi tiết kết quả xét nghiệm */}
            <div className="mt-4 rounded-control border border-line bg-surface-muted p-3">
              {/* Tên xét nghiệm */}
              <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-soft">
                {selected.test_name}
              </h4>
              {/* Giá trị kết quả + đơn vị */}
              <div className="mt-2 flex items-baseline gap-2">
                {/* Giá trị kết quả, chữ to */}
                <span className="text-2xl font-semibold text-ink">
                  {selected.result_value ?? selected.result_numeric ?? "—"}
                </span>
                {/* Đơn vị đo (nếu có) */}
                {selected.result_unit && (
                  <span className="text-sm text-ink-muted">
                    {selected.result_unit}
                  </span>
                )}
              </div>
              {/* Khoảng tham chiếu (nếu có) */}
              {(selected.reference_range_low != null ||
                selected.reference_range_high != null) && (
                <div className="mt-1 text-xs text-ink-muted">
                  Tham chiếu: {selected.reference_range_low ?? "—"} –{" "}
                  {selected.reference_range_high ?? "—"}
                </div>
              )}
              {/* Cờ đánh dấu (nếu có) */}
              {selected.flag && (
                <div className="mt-2">
                  {/* Badge cờ đánh dấu với màu theo mức độ */}
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      // Nguy kịch thì màu đỏ
                      selected.flag === "CRITICAL_HIGH" ||
                      selected.flag === "CRITICAL_LOW"
                        ? "bg-danger-bg text-danger"
                        : // Bất thường thì màu vàng
                          selected.flag !== "NORMAL"
                          ? "bg-warning-bg text-warning"
                          : // Bình thường thì màu xanh
                            "bg-success-bg text-success"
                    }`}
                  >
                    {/* Nhãn cờ đánh dấu */}
                    {FLAG_LABEL[selected.flag] ?? selected.flag}
                  </span>
                </div>
              )}
            </div>

            {/* Các nút hành động: ký duyệt / trả lại */}
            <div className="mt-4 flex gap-2">
              {/* Nút ký duyệt (chưa có chức năng) */}
              <button className="rounded-control bg-brand-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-700">
                Ký duyệt & cho phép trả kết quả
              </button>
              {/* Nút trả lại chỉnh sửa (chưa có chức năng) */}
              <button className="rounded-control border border-line bg-surface px-4 py-2 text-sm font-medium text-ink transition-colors hover:bg-surface-muted">
                Trả lại chỉnh sửa
              </button>
            </div>
            {/* Ghi chú về việc cần API backend */}
            <p className="mt-2 text-xs text-ink-faint">
              Ghi chú: hành động ký duyệt cần API backend (FastAPI service) để
              cập nhật is_finalized + reviewed_by_staff_id.
            </p>
          </div>
        ) : (
          // Nếu chưa chọn kết quả nào thì hiển thị thông báo
          <div className="flex h-full items-center justify-center rounded-control border border-dashed border-line text-sm text-ink-faint">
            Chọn một kết quả để duyệt
          </div>
        )}
      </section>
    </div>
  );
}