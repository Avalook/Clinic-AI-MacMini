"use client";

// Khu CHECK-IN trên trang chủ (thay cho mục sidebar cũ). Nút bấm → mở danh sách
// check-in HÔM NAY ngay dưới nút. Chỉ vai lâm sàng được bấm TÊN bệnh nhân để mở
// hồ sơ ở cột PHẢI; vai vận hành thao tác check-in ngay trên danh sách.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { UserCheck, ChevronDown, Search, FileText } from "lucide-react";
import { fmtTime, isVnMidnight } from "../../../lib/datetime";
import { unaccentVi } from "../../../lib/validation";
import { chipClass, type ChipTone } from "@/components/ui/Chip";
import Button from "@/components/ui/Button";
import NutInPhieu from "@/components/ui/NutInPhieu";
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
  /** CHỈ vai lâm sàng được mở/ghi hồ sơ. Vai vận hành chỉ dùng nút check-in. */
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
  // Thứ tự khám do backend quyết — màn hình chỉ hiển thị.
  const shown = [...filtered].sort(
    (a, b) => (a.call_order ?? 0) - (b.call_order ?? 0),
  );
  const sel = canWriteClinical
    ? (rows.find((r) => r.id === selId) ?? null)
    : null;

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
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint"
        />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Tìm tên, mã BN, SĐT..."
          className="h-10 w-full rounded-lg border border-brand-100 bg-white pl-9 pr-3 text-sm text-ink outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-600/15"
        />
      </div>
      {error && (
        <div className="rounded-md bg-danger-bg px-3 py-2 text-xs text-danger">
          {error}
        </div>
      )}
      {shown.length === 0 ? (
        <p className="px-2 py-6 text-center text-sm text-ink-faint">
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
                    ? "border-brand-600 ring-2 ring-brand-600/20"
                    : completed
                      ? "border-line bg-surface-muted"
                      : checkedIn
                        ? "border-success-bg"
                        : "border-brand-100")
                }
              >
                <div className="flex w-12 shrink-0 flex-col items-center">
                  <span className="text-xs font-semibold text-ink">
                    {isVnMidnight(r.slot_start) ? "—" : fmtTime(r.slot_start)}
                  </span>
                  {r.queue_number && (
                    <span className={`mt-0.5 ${chipClass("brand")}`}>
                      {r.queue_number}
                    </span>
                  )}
                </div>
                <button
                  onClick={() => {
                    if (canWriteClinical) setSelId(r.id);
                  }}
                  disabled={!canWriteClinical}
                  className="flex min-w-0 flex-1 items-start gap-1.5 text-left disabled:cursor-default"
                >
                  {canWriteClinical && (
                    <FileText size={13} className="mt-0.5 shrink-0 text-brand-600" />
                  )}
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-ink hover:text-brand-600">
                      {r.patient?.full_name ?? "—"}
                    </span>
                    <span className="block truncate text-label text-ink-muted">
                      <span className="font-mono">{r.patient?.patient_code}</span>
                      {r.patient?.phone_primary ? ` · ${r.patient.phone_primary}` : ""}
                      {r.service?.name ? ` · ${r.service.name}` : ""}
                    </span>
                  </span>
                </button>
                {/* Cột TRẠNG THÁI (nhãn VN) — tone chip theo pha. */}
                <span
                  className={`shrink-0 ${chipClass(
                    (completed
                      ? "neutral"
                      : checkedIn
                        ? "success"
                        : r.status === "SCHEDULED"
                          ? "warning"
                          : canCheckIn
                            ? "brand"
                            : "neutral") satisfies ChipTone,
                  )}`}
                >
                  {statusVN}
                </span>

                {/* Cột NÚT HÀNH ĐỘNG — đổi theo pha (mỗi pha 1 việc thật).
                    Chế độ vitals (ĐD): KHÔNG có nút check-in/xác nhận/không-đến — chỉ
                    mở BN để nhập sinh hiệu; vẫn cho "In phiếu" khi đã khám xong. */}
                {!canCheckinActions ? (
                  completed ? (
                    <NutInPhieu href={`/print/${r.id}`} size="md" />
                  ) : null
                ) : completed ? (
                  // Đã khám xong — Lễ tân in phiếu khám bệnh (tab mới → Xuất PDF).
                  <NutInPhieu href={`/print/${r.id}`} size="md" />
                ) : checkedIn ? (
                  // Đã check-in = ĐÃ vào hàng khám của bác sĩ. Không có nút đổi pha
                  // ở đây (việc khám là của bác sĩ); chỉ cho Hoàn tác nếu nhầm.
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <span className={chipClass("success")}>
                      Đang chờ bác sĩ khám
                    </span>
                    <button
                      onClick={() => act(r.id, "undo_checkin")}
                      disabled={busyId === r.id}
                      className="text-label text-ink-faint hover:text-ink-muted disabled:opacity-50"
                    >
                      Hoàn tác check-in
                    </button>
                  </div>
                ) : canCheckIn ? (
                  // Đã xác nhận/Chưa xác nhận, BN chưa đến → BN tới quầy thì Check-in.
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <Button
                      variant="primary"
                      onClick={() => act(r.id, "checkin")}
                      disabled={busyId === r.id}
                    >
                      {busyId === r.id ? "..." : "Check-in"}
                    </Button>
                    <button
                      onClick={() => act(r.id, "no_show")}
                      disabled={busyId === r.id}
                      className="text-label text-ink-faint hover:text-danger disabled:opacity-50"
                    >
                      Không đến
                    </button>
                  </div>
                ) : (
                  // NO_SHOW / CANCELLED / DOCTOR_DECLINED — không thao tác từ hàng đợi.
                  <span className="shrink-0 text-label text-ink-faint">—</span>
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
        className="flex w-full items-center gap-2 rounded-xl border border-brand-100 bg-brand-100 px-4 py-2.5 text-sm font-semibold text-brand-800 transition-colors hover:bg-brand-100"
      >
        <UserCheck size={16} />
        {triggerLabel}
        <span className="rounded-chip bg-white px-2 py-0.5 text-meta font-medium text-brand-800">
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
          <div className="mt-3 overflow-hidden rounded-card border border-line bg-surface-selected shadow-card md:h-[78vh]">
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
          <div className="mt-3 overflow-auto rounded-card border border-line bg-surface-selected shadow-card md:h-[78vh]">
            {list}
          </div>
        ))}
    </section>
  );
}
