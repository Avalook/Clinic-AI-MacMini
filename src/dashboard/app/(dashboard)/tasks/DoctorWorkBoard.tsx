"use client";

// "Công việc của tôi" cho BÁC SĨ — LỊCH theo NGÀY (như board CSKH): cột Ngày · Giờ
// · Bệnh nhân · Phân loại · Trạng thái · Hành động; lọc theo KỲ (Hôm nay/Tuần/Tháng)
// + TRẠNG THÁI. Bấm tên BN → hồ sơ lâm sàng (ClinicalRecordForm) ở cột PHẢI
// (SplitPane). LUỒNG ĐƠN GIẢN (T-DASH-DOCTOR-CLEANUP-01): KHÔNG còn bước "Nhận/Từ
// chối lịch" — Lễ tân check-in → BN tự vào hàng BS (CHECKED_IN) → BS mở hồ sơ khám →
// điền Chuẩn đoán + Lời dặn rồi Lưu thì lịch TỰ COMPLETED (không nút "Khám xong").

import { useState } from "react";
import { FileText, Printer } from "lucide-react";
import { fmtTimeOrNone } from "../../../lib/datetime";
import { compareQueue } from "../../../lib/queue";
import {
  todayVn,
  currentWeekStartVn,
  shiftWeek,
  weekDates,
  dayLabel,
  fmtDayMonth,
} from "../../../lib/roster";
import { daysInMonth } from "../../../lib/validation";
import StatusBadge from "../StatusBadge";
import ClinicalRecordForm from "./ClinicalRecordForm";
import SplitPane from "../SplitPane";

export interface DoctorApptRow {
  id: string;
  slot_start: string;
  status: string;
  /** Số thứ tự khám (queue_number) — lễ tân cấp khi check-in. */
  queue_number?: string | null;
  /** "Khám lần đầu" | "Tái khám" | "" — suy từ lịch sử hẹn (server tính sẵn). */
  phan_loai?: string;
  patient: {
    clinic_patient_id: string;
    patient_code: string;
    full_name: string;
    date_of_birth: string | null;
    phone_primary: string | null;
    phone_secondary: string | null;
    gender: string | null;
    ethnicity: string | null;
    nationality: string | null;
    occupation: string | null;
    patient_objection: string | null;
    address: string | null;
    guardian_name: string | null;
  } | null;
  service: { name: string } | null;
  /** Kênh đặt — "WALK_IN" = vãng lai; còn lại = đặt hẹn online. Cho THỨ TỰ GỌI (Model ②). */
  booking_channel?: string | null;
  /** Mốc giờ ĐẾN thật (visit.checked_in_at). Cho THỨ TỰ GỌI ưu tiên người có hẹn đúng giờ. */
  checked_in_at?: string | null;
  /** ĐÃ có KQ lab về hết → chờ bác sĩ đọc (B3). callRank kéo lên đầu (T-QUEUE-B3). */
  b3_ready?: boolean | null;
}

const STATUS_GROUPS: { key: string; label: string; statuses: string[] }[] = [
  { key: "all", label: "Tất cả", statuses: [] },
  { key: "pending", label: "Chờ xác nhận", statuses: ["SCHEDULED", "CSKH_CONFIRMED"] },
  { key: "confirmed", label: "Đã xác nhận / đến", statuses: ["CONFIRMED", "CHECKED_IN"] },
  { key: "done", label: "Đã khám xong", statuses: ["COMPLETED"] },
  { key: "off", label: "Từ chối / Hủy", statuses: ["DOCTOR_DECLINED", "CANCELLED", "NO_SHOW"] },
];
const PERIODS: { key: string; label: string }[] = [
  { key: "all", label: "Tất cả" },
  { key: "today", label: "Hôm nay" },
  { key: "week", label: "Tuần này" },
  { key: "next", label: "Tuần sau" },
  { key: "month", label: "Tháng này" },
];

function PhanLoai({ value }: { value?: string }) {
  if (!value) return <span className="text-[#c9a3b8]">—</span>;
  const first = value === "Khám lần đầu";
  return (
    <span
      className={
        "inline-block rounded-full px-2 py-0.5 text-[10px] font-medium " +
        (first ? "bg-[#dcfce7] text-[#15803d]" : "bg-[#fef3c7] text-[#b45309]")
      }
    >
      {value}
    </span>
  );
}

const CELL = "border-b border-r border-[#f3cfe0] px-2 py-1.5 align-top";

export default function DoctorWorkBoard({
  rows,
  staffId,
  readOnly = false,
  canEditAdmin = false,
  showPreVisitBrief = false,
  showSono = false,
  vitalsOnly = false,
}: {
  rows: DoctorApptRow[];
  staffId: string | null;
  /** Lễ tân: clone giao diện bác sĩ nhưng CHỈ XEM — ẩn Nhận/Từ chối, hồ sơ
   *  mở ở chế độ chỉ-đọc. Mặc định false (bác sĩ thao tác bình thường). */
  readOnly?: boolean;
  /** Cho sửa mục I Hành chính trong hồ sơ (vd Lễ tân) — độc lập với readOnly. */
  canEditAdmin?: boolean;
  /** Hiện nút "Xem tóm tắt trước khám" trong hồ sơ — chỉ BÁC SĨ bật từ server. */
  showPreVisitBrief?: boolean;
  /** Hiện form số đo siêu âm thai — chỉ Bác sĩ Siêu âm (server bật theo vai). */
  showSono?: boolean;
  vitalsOnly?: boolean;
}) {
  const [openId, setOpenId] = useState<string | null>(null);
  const [period, setPeriod] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  const open = rows.find((a) => a.id === openId) ?? null;

  // ---- Lọc theo KỲ + TRẠNG THÁI; gom theo NGÀY, trong ngày theo thứ tự khám ----
  const vnDate = (iso: string) =>
    new Date(new Date(iso).getTime() + 7 * 3_600_000).toISOString().slice(0, 10);
  const today = todayVn();
  const wk = weekDates(currentWeekStartVn());
  const nwk = weekDates(shiftWeek(currentWeekStartVn(), 1));
  const monthStart = today.slice(0, 7) + "-01";
  const monthEnd =
    today.slice(0, 7) +
    "-" +
    String(
      daysInMonth(Number(today.slice(5, 7)), Number(today.slice(0, 4))),
    ).padStart(2, "0");
  const RANGE: Record<string, [string, string] | null> = {
    all: null,
    today: [today, today],
    week: [wk[0], wk[6]],
    next: [nwk[0], nwk[6]],
    month: [monthStart, monthEnd],
  };
  const statusGroup = STATUS_GROUPS.find((g) => g.key === statusFilter);
  const range = RANGE[period];
  const filtered = rows
    .filter((r) => {
      const d = vnDate(r.slot_start);
      if (range && (d < range[0] || d > range[1])) return false;
      if (
        statusGroup &&
        statusGroup.statuses.length &&
        !statusGroup.statuses.includes(r.status)
      )
        return false;
      return true;
    })
    .sort((a, b) => {
      const da = vnDate(a.slot_start);
      const db = vnDate(b.slot_start);
      if (da !== db) return da < db ? -1 : 1;
      return compareQueue(a, b); // trong ngày: ƯT → số → giờ
    });

  const boardEl = (
    <div className="min-w-0 flex-1 space-y-2">
      {/* Lọc KỲ + TRẠNG THÁI */}
      <div className="flex flex-wrap items-center gap-1.5">
        {PERIODS.map((p) => (
          <button
            key={p.key}
            onClick={() => setPeriod(p.key)}
            className={
              "rounded-full px-3 py-1 text-xs font-medium transition-colors " +
              (period === p.key
                ? "bg-[#ec4899] text-white"
                : "border border-[#f3cfe0] bg-white text-[#9d2463] hover:bg-[#fdf2f8]")
            }
          >
            {p.label}
          </button>
        ))}
        <span className="px-0.5 text-[#d4d4d8]">·</span>
        {STATUS_GROUPS.map((g) => (
          <button
            key={g.key}
            onClick={() => setStatusFilter(g.key)}
            className={
              "rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors " +
              (statusFilter === g.key
                ? "bg-[#9d2463] text-white"
                : "border border-[#f3cfe0] bg-white text-[#9d2463] hover:bg-[#fdf2f8]")
            }
          >
            {g.label}
          </button>
        ))}
      </div>

      {/* Bảng lịch — khung kéo co dãn + cuộn (co thì cuộn, không vỡ cấu trúc). */}
      <div className="overflow-auto rounded-xl border border-[#f3cfe0] bg-white shadow-[0_1px_3px_rgba(236,72,153,0.08)] max-h-[78vh] min-h-[200px] max-w-full">
        <table className="w-full min-w-max border-collapse text-xs">
          <thead className="sticky top-0 z-10 bg-[#fce7f3] text-left text-[10px] font-semibold uppercase tracking-wide text-[#9d2463]">
            <tr>
              <th className="border-b border-r border-[#f3cfe0] px-2 py-1.5 min-w-[96px]">Ngày</th>
              <th className="border-b border-r border-[#f3cfe0] px-2 py-1.5 min-w-[64px]">Giờ</th>
              <th className="border-b border-r border-[#f3cfe0] px-2 py-1.5 min-w-[190px]">Bệnh nhân</th>
              <th className="border-b border-r border-[#f3cfe0] px-2 py-1.5 min-w-[96px]">Phân loại</th>
              <th className="border-b border-r border-[#f3cfe0] px-2 py-1.5 min-w-[110px]">Trạng thái</th>
              <th className="border-b border-[#f3cfe0] px-2 py-1.5 min-w-[150px]">Hành động</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-3 py-8 text-center text-xs text-[#a1a1aa]">
                  Không có lịch trong kỳ / trạng thái đã chọn.
                </td>
              </tr>
            ) : (
              filtered.map((a, i) => {
                const d = vnDate(a.slot_start);
                const newDay = i === 0 || vnDate(filtered[i - 1].slot_start) !== d;
                const active = openId === a.id;
                return (
                  <tr
                    key={a.id}
                    className={active ? "bg-[#fce7f3]" : i % 2 ? "bg-[#fdf7fb]" : "bg-white"}
                  >
                    <td className={`${CELL} whitespace-nowrap font-medium text-[#9d2463]`}>
                      {newDay ? `${dayLabel(d)} · ${fmtDayMonth(d)}` : ""}
                    </td>
                    <td className={`${CELL} whitespace-nowrap text-[#171717]`}>
                      {a.queue_number ? (
                        <span className="mr-1 rounded-full bg-[#fce7f3] px-1.5 text-[10px] font-medium text-[#9d2463]">
                          {a.queue_number}
                        </span>
                      ) : null}
                      {fmtTimeOrNone(a.slot_start)}
                    </td>
                    <td className={`${CELL}`}>
                      <button
                        onClick={() => setOpenId(a.id)}
                        className="flex items-start gap-1.5 text-left"
                      >
                        <FileText size={13} className="mt-0.5 shrink-0 text-[#ec4899]" />
                        <span>
                          <span className="block font-medium text-[#171717] hover:text-[#ec4899]">
                            {a.patient?.full_name ?? "—"}
                          </span>
                          <span className="block font-mono text-[10px] text-[#888888]">
                            {a.patient?.patient_code}
                            {a.patient?.phone_primary ? ` · ${a.patient.phone_primary}` : ""}
                            {a.service?.name ? ` · ${a.service.name}` : ""}
                          </span>
                        </span>
                      </button>
                    </td>
                    <td className={CELL}>
                      <div className="flex flex-col items-start gap-1">
                        {a.b3_ready && (
                          <span className="rounded-full bg-[#fef3c7] px-2 py-0.5 text-[10px] font-medium text-[#b45309]">
                            🔔 Chờ đọc KQ
                          </span>
                        )}
                        <PhanLoai value={a.phan_loai} />
                      </div>
                    </td>
                    <td className={CELL}>
                      <StatusBadge status={a.status} />
                    </td>
                    <td className={`${CELL} whitespace-nowrap`}>
                      {readOnly ? (
                        // LỄ TÂN chỉ-đọc: không Nhận/Từ chối/khám. Xem hồ sơ + In phiếu (đều read-only).
                        <span className="flex gap-1">
                          <button
                            onClick={() => setOpenId(a.id)}
                            className="inline-flex min-h-8 items-center gap-1 rounded-md border border-[#f3cfe0] bg-white px-2.5 text-xs font-medium text-[#9d2463] hover:bg-[#fdf2f8]"
                          >
                            <FileText size={12} /> Xem hồ sơ
                          </button>
                          {a.status === "COMPLETED" && (
                            <a
                              href={`/print/${a.id}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex min-h-8 items-center gap-1 rounded-md border border-[#bbf7d0] bg-white px-2.5 text-xs font-semibold text-[#15803d] hover:bg-[#f0fdf4]"
                            >
                              <Printer size={12} /> In phiếu
                            </a>
                          )}
                        </span>
                      ) : a.status === "CHECKED_IN" ? (
                        <button
                          onClick={() => setOpenId(a.id)}
                          className="inline-flex min-h-8 items-center gap-1 rounded-md bg-[#7c3aed] px-2.5 text-xs font-semibold text-white hover:bg-[#6d28d9]"
                        >
                          Mở hồ sơ → khám
                        </button>
                      ) : a.status === "SCHEDULED" ||
                        a.status === "CSKH_CONFIRMED" ||
                        a.status === "CONFIRMED" ? (
                        <span className="text-[11px] text-[#a1a1aa]">Chờ lễ tân check-in</span>
                      ) : a.status === "COMPLETED" ? (
                        <a
                          href={`/print/${a.id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex min-h-8 items-center gap-1 rounded-md border border-[#bbf7d0] bg-white px-2.5 text-xs font-semibold text-[#15803d] hover:bg-[#f0fdf4]"
                        >
                          <Printer size={12} /> In phiếu
                        </a>
                      ) : (
                        <span className="text-[11px] text-[#a1a1aa]">—</span>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );

  return (
    <>
      {open ? (
        <>
          <p className="mb-2 text-[11px] text-[#c084a8]">
            ↔ Kéo thanh hồng ở GIỮA 2 bảng để chỉnh độ rộng (kéo trái: bảng trái
            co, hồ sơ rộng ra).
          </p>
          <SplitPane
            className="md:h-[78vh]"
            initialLeftPct={52}
            left={boardEl}
            right={
              <ClinicalRecordForm
                key={open.id}
                appt={open}
                staffId={staffId}
                fill
                readOnly={readOnly}
                vitalsOnly={vitalsOnly}
                canEditAdmin={canEditAdmin}
                showPreVisitBrief={showPreVisitBrief}
                showSono={showSono}
                /* Bác sĩ / TKYK (+ Lễ tân chỉ-đọc): pager ◀ ▶ xem lượt khám
                   trước/sau của BN ngay trong phiếu (chỉ đọc). */
                enableVisitPager
                onClose={() => setOpenId(null)}
              />
            }
          />
        </>
      ) : (
        boardEl
      )}
    </>
  );
}
