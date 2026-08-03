// Thời lượng khám THỰC TẾ, đặt ngay cạnh chỗ chỉnh số chỗ.
//
// VÌ SAO NÓ Ở ĐÂY. Trưởng ca đang quyết "khung 18:00 cho mấy chỗ". Cho tới giờ
// họ quyết bằng cảm giác, vì con số duy nhất hệ thống từng đưa ra là bảng phút
// viết cứng trong mã (khách mới 15', tái khám 5') — bốn con số không đến từ phép
// đo nào. Nếu BS Thành thật sự mất 22 phút cho một khách mới lúc 18:00 thứ Ba,
// không có chỗ nào trong sản phẩm nói điều đó ra.
//
// Bảng dưới đây đọc từ v_consultation_duration_stats: trung vị và p90 tính từ
// chính các lần bấm "Bắt đầu" / "Hoàn tất" ở bàn khám. Không ai nhập, không ai
// đoán.
//
// TRUNG VỊ VÀ p90, KHÔNG PHẢI TRUNG BÌNH. Một ca 90 phút vì biến chứng kéo trung
// bình cả khung lên và mô tả sai một buổi bình thường. Trung vị trả lời "một ca
// điển hình mất bao lâu"; p90 trả lời "cần bao nhiêu để hiếm khi vỡ lịch". Xếp
// lịch cần cả hai con số, và chúng nói hai chuyện khác nhau.
//
// sample_count LUÔN HIỆN, và đó không phải chi tiết phụ. Trung vị của 3 ca không
// đáng để chỉnh lịch cả tháng theo. Con số nhỏ được làm mờ đi chứ không giấu —
// giấu thì người đọc tưởng mọi dòng đều đáng tin như nhau.

import { ScanLine } from "lucide-react";

export interface DurationStatRow {
  doctor_name: string | null;
  vn_weekday: number | null;
  vn_hour: number | null;
  patient_kind: string | null;
  sample_count: number;
  median_minutes: number | null;
  p90_minutes: number | null;
}

const DOW = ["CN", "T2", "T3", "T4", "T5", "T6", "T7"];

/** Dưới ngưỡng này thì con số chỉ là gợi ý, chưa phải bằng chứng. */
const WEAK_SAMPLE = 10;

const KIND_LABEL: Record<string, string> = {
  NEW: "Khám mới",
  RETURN: "Tái khám",
};

export default function MeasuredDurationCard({
  rows,
}: {
  rows: DurationStatRow[];
}) {
  return (
    <section className="rounded-card border border-line bg-surface shadow-card">
      <header className="border-b border-line px-5 py-3">
        <h2 className="flex items-center gap-2 font-medium text-ink">
          <ScanLine size={16} className="text-brand-600" />
          Thời gian khám thực tế
        </h2>
        <p className="mt-0.5 text-xs text-ink-muted">
          Đo từ lúc bàn khám bấm &ldquo;Bắt đầu&rdquo; đến lúc bấm &ldquo;Hoàn
          tất&rdquo; — không phải con số cấu hình. Dùng để cân số chỗ mỗi khung
          bên trên.
        </p>
      </header>

      {rows.length === 0 ? (
        <div className="px-5 py-8 text-center text-sm text-ink-muted">
          <p className="font-medium text-ink">Chưa có số liệu</p>
          <p className="mt-1">
            Bảng này đầy lên khi bàn khám dùng nút Bắt đầu / Hoàn tất trên các
            màn hình quy trình. Chưa đủ dữ liệu thì để trống — một con số bịa
            còn tệ hơn không có con số nào.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-[13px] text-ink-muted">
                <th className="px-5 py-2 font-medium">Bác sĩ</th>
                <th className="px-3 py-2 font-medium">Khung</th>
                <th className="px-3 py-2 font-medium">Loại khách</th>
                <th className="px-3 py-2 font-medium">Trung vị</th>
                <th className="px-3 py-2 font-medium">p90</th>
                <th className="px-5 py-2 font-medium">Số ca</th>
              </tr>
            </thead>
            <tbody className="tabular-nums">
              {rows.map((r, i) => {
                const weak = r.sample_count < WEAK_SAMPLE;
                return (
                  <tr
                    key={i}
                    className={`border-b border-line last:border-0 ${
                      weak ? "opacity-60" : ""
                    }`}
                  >
                    <td className="px-5 py-2 text-ink">
                      {r.doctor_name ?? "—"}
                    </td>
                    <td className="px-3 py-2 text-ink-soft">
                      {r.vn_weekday !== null ? DOW[r.vn_weekday] : "—"}{" "}
                      {r.vn_hour !== null
                        ? `${String(r.vn_hour).padStart(2, "0")}:00`
                        : ""}
                    </td>
                    <td className="px-3 py-2 text-ink-soft">
                      {r.patient_kind
                        ? (KIND_LABEL[r.patient_kind] ?? r.patient_kind)
                        : "—"}
                    </td>
                    <td className="px-3 py-2 font-medium text-ink">
                      {r.median_minutes ?? "—"}′
                    </td>
                    <td className="px-3 py-2 text-ink-soft">
                      {r.p90_minutes ?? "—"}′
                    </td>
                    <td className="px-5 py-2 text-ink-muted">
                      {r.sample_count}
                      {weak && (
                        <span className="ml-1.5 text-xs">(chưa đủ)</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <p className="border-t border-line px-5 py-2.5 text-xs text-ink-faint">
        Dòng mờ = dưới {WEAK_SAMPLE} ca, chưa đủ để kết luận. Bảng này cũng là
        dữ liệu đầu vào cho phần đề xuất số chỗ tự động về sau.
      </p>
    </section>
  );
}
