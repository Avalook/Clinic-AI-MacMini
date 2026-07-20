"use client";

// Khu CHECK-IN trên trang chủ (thay cho mục sidebar cũ). Nút bấm → mở danh sách
// check-in HÔM NAY ngay dưới nút; bấm TÊN bệnh nhân → hồ sơ lâm sàng hiện ở cột
// PHẢI (SplitPane: kéo thanh giữa, bảng này dãn bảng kia co). Người đón khám
// (ĐD/Lễ tân/Quản lý) ghi được Sinh hiệu, các mục khác read-only.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { UserCheck, ChevronDown, Search, FileText, Printer } from "lucide-react";
import { fmtTime, isVnMidnight } from "../../../lib/datetime";
import { unaccentVi } from "../../../lib/validation";
import { compareQueue } from "../../../lib/queue";
import SplitPane from "../SplitPane";
import ClinicalRecordForm from "../tasks/ClinicalRecordForm";
import type { DoctorApptRow } from "../tasks/DoctorWorkBoard";

export interface HomeCheckinRow extends DoctorApptRow {
  queue_number: string | null;
}

// Nhãn trạng thái buổi khám (VN) cho cột "Trạng thái" của hàng đợi Lễ tân.
const STATUS_VN: Record<string, string> = {
  SCHEDULED: "Chưa xác nhận",
  CSKH_CONFIRMED: "Đã xác nhận",
  CONFIRMED: "Đã xác nhận",
  CHECKED_IN: "Đã check-in",
  COMPLETED: "Đã khám xong",
  NO_SHOW: "Không đến",
  CANCELLED: "Đã huỷ",
  DOCTOR_DECLINED: "Bác sĩ từ chối",
};

export default function HomeCheckin({
  rows,
  staffId,
  canWriteClinical = false,
  defaultOpen = false,
  canCheckinActions = true,
  triggerLabel = "Check-in bệnh nhân",
}: {
  rows: HomeCheckinRow[];
  staffId: string | null;
  /** CHỈ Bác sĩ + Điều dưỡng được ghi lâm sàng (sinh hiệu + lý do khám). Lễ tân /
   *  Quản lý vẫn check-in (hành chính) nhưng xem hồ sơ lâm sàng ở chế độ chỉ-đọc. */
  canWriteClinical?: boolean;
  defaultOpen?: boolean;
  /** Hiện cụm nút check-in/xác nhận/không-đến. Điều dưỡng (chế độ "Sinh hiệu hôm
   *  nay") = false → CHỈ mở BN để nhập sinh hiệu, KHÔNG có nút check-in (đó là việc
   *  Lễ tân). */
  canCheckinActions?: boolean;
  /** Nhãn nút mở khu (vd "Sinh hiệu bệnh nhân hôm nay" cho ĐD). */
  triggerLabel?: string;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(defaultOpen);
  const [q, setQ] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selId, setSelId] = useState<string | null>(null);

  // "Đã đến" gồm CẢ check-in (đang chờ khám) lẫn đã khám xong — vì khách thực
  // sự đã có mặt trong ngày. Lễ tân/QL nhìn số này để biết tổng khách đến.
  const arrived = rows.filter(
    (r) => r.status === "CHECKED_IN" || r.status === "COMPLETED",
  ).length;
  // Tìm tên KHÔNG phân biệt dấu (D11): so khớp trên bản đã bỏ dấu cả 2 phía.
  const term = unaccentVi(q.trim());
  const filtered = term
    ? rows.filter((r) => {
        const p = r.patient;
        return (
          unaccentVi(p?.full_name ?? "").includes(term) ||
          unaccentVi(p?.patient_code ?? "").includes(term) ||
          (p?.phone_primary ?? "").includes(term)
        );
      })
    : rows;
  // Thứ tự khám: ƯT lên đầu → số → theo giờ.
  const shown = [...filtered].sort(compareQueue);
  const sel = rows.find((r) => r.id === selId) ?? null;

  // Mọi nút = 1 việc thật → 1 action trên route /api/appointments (tái dùng,
  // service-role, gate canWriteIntake/canCheckin). Chặn double-click qua busyId.
  async function act(
    id: string,
    action: "cskh_confirm" | "checkin" | "undo_checkin" | "no_show",
  ) {
    if (busyId) return; // đang có 1 việc chạy → chặn double-click
    setBusyId(id);
    setError(null);
    const res = await fetch("/api/appointments", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, action }),
    });
    setBusyId(null);
    if (!res.ok) {
      setError((await res.json()).error ?? "Có lỗi xảy ra.");
      return;
    }
    router.refresh();
  }

  const list = (
    <div className="space-y-2 p-2">
      <div className="relative">
        <Search
          size={15}
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#a1a1aa]"
        />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Tìm tên, mã BN, SĐT..."
          className="h-10 w-full rounded-lg border border-[#f3cfe0] bg-white pl-9 pr-3 text-sm text-[#171717] outline-none focus:border-[#ec4899] focus:ring-2 focus:ring-[#ec4899]/15"
        />
      </div>
      {error && (
        <div className="rounded-md bg-[#fee2e2] px-3 py-2 text-xs text-[#dc2626]">
          {error}
        </div>
      )}
      {shown.length === 0 ? (
        <p className="px-2 py-6 text-center text-sm text-[#a1a1aa]">
          {rows.length === 0
            ? "Hôm nay chưa có lịch hẹn."
            : "Không tìm thấy bệnh nhân."}
        </p>
      ) : (
        <ul className="space-y-2">
          {shown.map((r) => {
            const checkedIn = r.status === "CHECKED_IN";
            const completed = r.status === "COMPLETED";
            // Hàng đợi đón khách theo PHA (mỗi pha 1 nút việc):
            //   SCHEDULED          → "Gọi xác nhận" (cskh_confirm)
            //   CSKH_CONFIRMED/CONFIRMED → "Check-in" (BN đã tới)
            //   CHECKED_IN         → đã vào hàng khám của bác sĩ (chỉ Hoàn tác)
            const canCheckIn = ["SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED"].includes(r.status);
            const statusVN = STATUS_VN[r.status] ?? r.status;
            const active = selId === r.id;
            return (
              <li
                key={r.id}
                className={
                  "flex items-center gap-3 rounded-xl border bg-white p-2.5 " +
                  (active
                    ? "border-[#ec4899] ring-2 ring-[#ec4899]/20"
                    : completed
                      ? "border-[#e4e4e7] bg-[#fafafa]"
                      : checkedIn
                        ? "border-[#bbf7d0]"
                        : "border-[#f3cfe0]")
                }
              >
                <div className="flex w-12 shrink-0 flex-col items-center">
                  <span className="text-xs font-semibold text-[#171717]">
                    {isVnMidnight(r.slot_start) ? "—" : fmtTime(r.slot_start)}
                  </span>
                  {r.queue_number && (
                    <span className="mt-0.5 rounded-full bg-[#fce7f3] px-1.5 text-[10px] font-medium text-[#9d2463]">
                      {r.queue_number}
                    </span>
                  )}
                </div>
                <button
                  onClick={() => setSelId(r.id)}
                  className="flex min-w-0 flex-1 items-start gap-1.5 text-left"
                >
                  <FileText size={13} className="mt-0.5 shrink-0 text-[#ec4899]" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-[#171717] hover:text-[#ec4899]">
                      {r.patient?.full_name ?? "—"}
                    </span>
                    <span className="block truncate text-[11px] text-[#888888]">
                      <span className="font-mono">{r.patient?.patient_code}</span>
                      {r.patient?.phone_primary ? ` · ${r.patient.phone_primary}` : ""}
                      {r.service?.name ? ` · ${r.service.name}` : ""}
                    </span>
                  </span>
                </button>
                {/* Cột TRẠNG THÁI (nhãn VN) */}
                <span
                  className={
                    "shrink-0 rounded-full px-2.5 py-0.5 text-center text-[10px] font-medium " +
                    (completed
                      ? "bg-[#f4f4f5] text-[#52525b]"
                      : checkedIn
                        ? "bg-[#dcfce7] text-[#15803d]"
                        : r.status === "SCHEDULED"
                          ? "bg-[#fef9c3] text-[#a16207]"
                          : canCheckIn
                            ? "bg-[#fce7f3] text-[#9d2463]"
                            : "bg-[#f4f4f5] text-[#52525b]")
                  }
                >
                  {statusVN}
                </span>

                {/* Cột NÚT HÀNH ĐỘNG — đổi theo pha (mỗi pha 1 việc thật).
                    Chế độ vitals (ĐD): KHÔNG có nút check-in/xác nhận/không-đến — chỉ
                    mở BN để nhập sinh hiệu; vẫn cho "In phiếu" khi đã khám xong. */}
                {!canCheckinActions ? (
                  completed ? (
                    <a
                      href={`/print/${r.id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex min-h-8 shrink-0 items-center gap-1 rounded-lg border border-[#bbf7d0] bg-white px-2.5 text-xs font-semibold text-[#15803d] hover:bg-[#f0fdf4]"
                    >
                      <Printer size={13} /> In phiếu
                    </a>
                  ) : null
                ) : completed ? (
                  // Đã khám xong — Lễ tân in phiếu khám bệnh (tab mới → Xuất PDF).
                  <a
                    href={`/print/${r.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex min-h-8 shrink-0 items-center gap-1 rounded-lg border border-[#bbf7d0] bg-white px-2.5 text-xs font-semibold text-[#15803d] hover:bg-[#f0fdf4]"
                  >
                    <Printer size={13} /> In phiếu
                  </a>
                ) : checkedIn ? (
                  // Đã check-in = ĐÃ vào hàng khám của bác sĩ. Không có nút đổi pha
                  // ở đây (việc khám là của bác sĩ); chỉ cho Hoàn tác nếu nhầm.
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <span className="rounded-full bg-[#dcfce7] px-2 py-0.5 text-center text-[10px] font-medium text-[#15803d]">
                      Đang chờ bác sĩ khám
                    </span>
                    <button
                      onClick={() => act(r.id, "undo_checkin")}
                      disabled={busyId === r.id}
                      className="text-[11px] text-[#a1a1aa] hover:text-[#71717a] disabled:opacity-50"
                    >
                      Hoàn tác check-in
                    </button>
                  </div>
                ) : canCheckIn ? (
                  // Đã xác nhận/Chưa xác nhận, BN chưa đến → BN tới quầy thì Check-in.
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <button
                      onClick={() => act(r.id, "checkin")}
                      disabled={busyId === r.id}
                      className="min-h-9 rounded-lg bg-[#ec4899] px-3 text-xs font-semibold text-white hover:bg-[#db2777] disabled:opacity-50"
                    >
                      {busyId === r.id ? "..." : "Check-in"}
                    </button>
                    <button
                      onClick={() => act(r.id, "no_show")}
                      disabled={busyId === r.id}
                      className="text-[11px] text-[#a1a1aa] hover:text-[#dc2626] disabled:opacity-50"
                    >
                      Không đến
                    </button>
                  </div>
                ) : (
                  // NO_SHOW / CANCELLED / DOCTOR_DECLINED — không thao tác từ hàng đợi.
                  <span className="shrink-0 text-[11px] text-[#c4c4c8]">—</span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );

  return (
    <section>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 rounded-xl border border-[#f3cfe0] bg-[#fce7f3] px-4 py-2.5 text-sm font-semibold text-[#9d2463] transition-colors hover:bg-[#fbcfe8]"
      >
        <UserCheck size={16} />
        {triggerLabel}
        <span className="rounded-full bg-white px-2 py-0.5 text-xs font-medium text-[#9d2463]">
          {arrived}/{rows.length} đã đến
        </span>
        <ChevronDown
          size={16}
          className={"ml-auto transition-transform " + (open ? "rotate-180" : "")}
        />
      </button>

      {open &&
        (sel ? (
          // Tách đôi: danh sách (trái) + hồ sơ (phải). KHUNG CỐ ĐỊNH chiều cao,
          // mỗi cột tự cuộn ĐỘC LẬP — lăn danh sách trái KHÔNG làm panel phải nhúc
          // nhích (panel tóm tắt giữ nguyên).
          <div className="mt-3 overflow-hidden rounded-xl border border-[#f3cfe0] bg-[#fdf2f8] shadow-[0_1px_3px_rgba(236,72,153,0.08)] md:h-[78vh]">
            <SplitPane
              className="h-full"
              left={list}
              right={
                <ClinicalRecordForm
                  key={sel.id}
                  appt={sel}
                  staffId={staffId}
                  vitalsOnly
                  readOnly={!canWriteClinical}
                  fill
                  onClose={() => setSelId(null)}
                />
              }
            />
          </div>
        ) : (
          <div className="mt-3 overflow-auto rounded-xl border border-[#f3cfe0] bg-[#fdf2f8] shadow-[0_1px_3px_rgba(236,72,153,0.08)] md:h-[78vh]">
            {list}
          </div>
        ))}
    </section>
  );
}
