"use client";

// Bảng "Trạng thái BN buổi khám" — READ-ONLY cho Lễ tân (front desk).
// List BN có buổi khám (visit) TẠO HÔM NAY, cột trạng thái theo visit.status
// (OPEN / IN_PROGRESS / INCOMPLETE / FINALIZED / AMENDED).
// CHỈ hiển thị, không nút ghi. Data server-fetch ở home/page.tsx, đọc thẳng Supabase
// (RLS SELECT visit_select_authenticated). Badge riêng cho visit — KHÔNG dùng StatusBadge
// (badge đó dành cho appointment.status, màu khác).

// 29/09/2026 (Tuyền chốt): cột 2 là HÀNH TRÌNH KHÁCH dạng gọn — "Đang ở / Đang
// chờ / Đã về" + tên phòng thật + thanh đoạn màu (máy chủ quyết, cùng hàm với
// màn Hành trình). Bấm dòng → khung đầy đủ trong popup. Thay thanh 4 mốc cũ.

import { useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import { MA_CON_O, type TrangThaiHienThi } from "@/lib/trang-thai-lich";
import type { HanhTrinhGon } from "@/lib/hanh-trinh-khach";

import {
  DongHanhTrinhGon,
  PopupHanhTrinhKhach,
  useBayGio,
} from "../_lam-viec/HanhTrinhKhach";
import { WaitClock } from "./VisitProgress";

// NHÃN TRẠNG THÁI DO MÁY CHỦ QUYẾT (30/09/2026 — Tuyền: "đã checkout rồi
// nhưng trang chủ vẫn ghi đang khám"). Bản trước tự suy ở đây từ visit.status
// + appointment.status + cờ đã thu, mà check-out không đổi cả hai cột ấy — nên
// khách đã về vẫn "Đang khám". Nay `trang_thai` (core/trang_thai_lich.py)
// cùng hàm với lưới lịch tuần và màn Quản lý khách hàng.

/** Đồng hồ chờ chạy khi khách còn ở phòng khám và chưa khám xong. */
function conCho(tt: TrangThaiHienThi | null | undefined): boolean {
  return Boolean(tt && MA_CON_O.includes(tt.ma) && tt.ma !== "KHAM_XONG");
}

export interface VisitStatusRow {
  visit_id: string;
  status: string;
  checked_in_at: string | null;
  created_at: string;
  patient: { full_name: string | null; patient_code: string | null } | null;
  doctor: { full_name: string | null } | null;
  service: { name: string | null } | null;
  /** appointment.status (join) — nguồn THẬT cho mốc "Khám xong" (COMPLETED). */
  appointment: { status: string | null } | null;
  /** Đã thu đủ mọi khâu (bảng payment) → mốc "Đã thanh toán" xanh. Server tính. */
  paid?: boolean;
  /** Mốc khám xong (mig 058) — dùng tính & hiện "khám N phút" cho board Lễ tân. */
  /** Lúc bác sĩ KÝ bệnh án — mốc kết thúc khám. Đọc `finalized_at` chứ không
   *  phải `exam_completed_at`: baseline khai cả hai cột cho cùng một việc,
   *  nhưng chỉ cột này được ghi (clinical_sign_service), và cột kia thậm chí
   *  không tồn tại trên prod. */
  finalized_at?: string | null;
  /** Lúc bệnh án đầu tiên của lượt được mở — mốc "Đang khám". Server gắn vào
   *  từ /api/v1/visits/progress. Trống khi chưa ai mở bệnh án. */
  exam_started_at?: string | null;
  /** Lúc thu xong khâu cuối — mốc "Đã thanh toán". Cùng nguồn với trên. */
  paid_at?: string | null;
  /** Lễ tân đã Check-out (máy chủ) — khách xong buổi: tick hết, dừng đồng hồ. */
  closed_at?: string | null;
  /** Mốc khám xong thật (`visit.exam_completed_at`). */
  kham_xong_luc?: string | null;
  /** Hành trình khách dạng gọn (máy chủ, 29/09/2026). */
  hanh_trinh?: HanhTrinhGon | null;
  /** Nhãn trạng thái máy chủ quyết (30/09/2026). */
  trang_thai?: TrangThaiHienThi | null;
}

/** Thời lượng khám (phút) = khám xong − bắt đầu khám. null nếu thiếu mốc. */
function examMinutes(
  checkedInAt: string | null,
  finalizedAt: string | null | undefined,
): number | null {
  if (!checkedInAt || !finalizedAt) return null;
  const ms = Date.parse(finalizedAt) - Date.parse(checkedInAt);
  if (!Number.isFinite(ms) || ms < 0) return null;
  return Math.round(ms / 60000);
}

// KHÔNG kẻ đường ngăn giữa các dòng (Quang chốt 06/08 — "bỏ các đường kẻ bảng
// đi, để trắng cho nhìn thoáng"). Dòng nào ra dòng nào vẫn phân biệt được nhờ
// khoảng thở dọc và nền sáng lên khi rê chuột.
const TH = "px-4 pb-2 pt-3 text-left font-semibold text-ink-soft";
const TD = "px-4 py-4 align-middle text-ink";

export default function VisitStatusBoard({ rows }: { rows: VisitStatusRow[] }) {
  const bayGio = useBayGio();
  const [mo, setMo] = useState<{ id: string; ten: string | null } | null>(null);
  return (
    <>
    <div className="overflow-auto rounded-card border border-line bg-surface shadow-card">
      <table className="w-full border-collapse text-sm sm:min-w-max">
        <thead>
          <tr>
            {/* Ô đầu: thông tin BN gộp. Còn lại: hành trình khách dạng gọn. */}
            <th className={`${TH} min-w-60`}>Bệnh nhân</th>
            <th className={`${TH} hidden min-w-85 sm:table-cell`}>Hành trình khách</th>
            <th className={`${TH} hidden sm:table-cell`}>
              <span className="sr-only">Xem hành trình</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td className="px-4 py-6 text-center text-ink-muted" colSpan={3}>
                Chưa có buổi khám nào hôm nay.
              </td>
            </tr>
          ) : (
            rows.map((r) => {
              const examMin = examMinutes(r.checked_in_at, r.finalized_at);
              return (
                <tr
                  key={r.visit_id}
                  className="cursor-pointer hover:bg-surface-muted"
                  onClick={() => setMo({ id: r.visit_id, ten: r.patient?.full_name ?? null })}
                >
                  {/* Ô 1 — thông tin gộp: tên BN + mã · bác sĩ · dịch vụ · trạng thái
                      (live badge) + đồng hồ chờ (đếm liên tục từ check-in). */}
                  <td className={TD}>
                    <div className="space-y-1">
                      <div className="flex items-baseline gap-1.5">
                        <span className="font-semibold text-ink">
                          {r.patient?.full_name ?? "—"}
                        </span>
                        {r.patient?.patient_code && (
                          <span className="font-mono text-xs text-ink-muted">
                            {r.patient.patient_code}
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-ink-muted">
                        <span className="text-ink-faint">BS:</span>{" "}
                        {r.doctor?.full_name ?? "—"}
                        <span className="mx-1 text-line-strong">·</span>
                        {r.service?.name ?? "—"}
                      </div>
                      <div className="flex flex-wrap items-center gap-2 pt-0.5">
                        {r.trang_thai && (
                          <Chip tone={r.trang_thai.tone}>{r.trang_thai.nhan}</Chip>
                        )}
                        <WaitClock
                          checkedInAt={r.checked_in_at}
                          active={!r.closed_at && conCho(r.trang_thai)}
                        />
                        {examMin !== null && (
                          <span
                            className="rounded-chip bg-status-in-progress-bg px-2 py-0.5 text-label font-medium text-status-in-progress tabular-nums"
                            title="Thời gian khám (khám xong − bắt đầu khám)"
                          >
                            khám {examMin} phút
                          </span>
                        )}
                      </div>
                      {/* Màn hẹp (375): hành trình nằm ngay dưới tên khách —
                          cột riêng ẩn đi, bấm dòng mở khung đầy đủ. */}
                      {r.hanh_trinh ? (
                        <div className="pt-2 sm:hidden">
                          <DongHanhTrinhGon gon={r.hanh_trinh} bayGio={bayGio} />
                        </div>
                      ) : null}
                    </div>
                  </td>
                  {/* Ô 2 — hành trình khách dạng gọn (máy chủ quyết). Đã
                      Check-out = xong buổi: thanh tick hết. */}
                  <td className={`${TD} hidden sm:table-cell`}>
                    {r.hanh_trinh ? (
                      <DongHanhTrinhGon gon={r.hanh_trinh} bayGio={bayGio} />
                    ) : (
                      <span className="text-meta text-ink-faint">—</span>
                    )}
                  </td>
                  {/* Màn hẹp: bấm cả dòng là mở — bỏ cột nút cho đỡ cuộn ngang. */}
                  <td className={`${TD} hidden text-right sm:table-cell`}>
                    <Button
                      size="sm"
                      variant="soft"
                      onClick={(e) => {
                        e.stopPropagation();
                        setMo({ id: r.visit_id, ten: r.patient?.full_name ?? null });
                      }}
                    >
                      Xem hành trình ›
                    </Button>
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
    {mo ? <PopupHanhTrinhKhach visitId={mo.id} ten={mo.ten} onDong={() => setMo(null)} /> : null}
    </>
  );
}
