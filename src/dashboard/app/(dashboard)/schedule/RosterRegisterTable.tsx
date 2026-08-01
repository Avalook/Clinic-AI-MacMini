"use client";

// "Đăng ký lịch làm việc" — bảng MA TRẬN tương tác (ngày × trạm, gom theo tầng,
// CÙNG layout với bảng "Lịch làm việc" read-only ở trên). Khác bảng trên ở chỗ:
//   - Hiện MỌI đăng ký của MỌI người + trạng thái (Chờ duyệt / Đã duyệt / Từ chối)
//     để ai cũng thấy lịch dự kiến của người khác mà tự liệu.
//   - Click 1 ô → modal "nảy ra" để tự đăng ký ca CỦA MÌNH ngay tại trạm+ngày đó.
//     Đăng ký xong → status PENDING (chờ quản lý duyệt), không lên lịch chung tới
//     khi được duyệt. Ca PENDING của chính mình có nút xoá.
// Ghi qua /api/roster (POST đăng ký, DELETE huỷ) rồi router.refresh().

import { useEffect, useId, useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { X, Trash2, Check } from "lucide-react";
import {
  STATIONS,
  STATION_SEGMENTS,
  STATION_LABEL,
  SHIFTS,
  SHIFT_LABEL,
  dayShort,
  fmtDayMonth,
  type Shift,
} from "../../../lib/roster";

export interface RegisterRow {
  id: string;
  work_date: string;
  station: string;
  shift: Shift;
  staff_id: string | null;
  staff_name: string;
  status: "PENDING" | "APPROVED" | "REJECTED";
  reject_reason: string | null;
}

const STATUS_BADGE: Record<RegisterRow["status"], { cls: string; label: string }> = {
  PENDING: { cls: "bg-warning-bg text-warning", label: "Chờ duyệt" },
  APPROVED: { cls: "bg-success-bg text-success", label: "Đã duyệt" },
  REJECTED: { cls: "bg-danger-bg text-danger", label: "Từ chối" },
};

const TH_BASE =
  "border-b border-r border-brand-100 px-2 py-2 text-center align-middle font-semibold text-brand-800";

function cellKey(date: string, station: string) {
  return `${date}|${station}`;
}

export default function RosterRegisterTable({
  weekStart,
  dates,
  rows,
  myStaffId,
  myStaffName,
  isApprover = false,
}: {
  weekStart: string;
  dates: string[];
  rows: RegisterRow[];
  /** staff_id người đang đăng nhập; null = chưa chọn danh tính (không đăng ký được). */
  myStaffId: string | null;
  /** Tên người đăng nhập — hiện ngay cho ca vừa đăng ký (optimistic). */
  myStaffName?: string;
  /** Quản lý hệ thống: hiện nút Duyệt / Từ chối ngay trong popup ô. */
  isApprover?: boolean;
}) {
  const router = useRouter();
  const dialogTitleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState<{ date: string; station: string } | null>(null);
  const [shift, setShift] = useState<Shift>("FULL");
  const [error, setError] = useState<string | null>(null);
  // Duyệt/từ chối ngay trong popup (chỉ Quản lý). rejectingId = ca đang mở ô lý do.
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [, startTransition] = useTransition();

  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const containDialogFocus = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(null);
      if (event.key !== "Tab") return;
      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable || focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && (active === first || !dialogRef.current?.contains(active))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", containDialogFocus);
    return () => {
      document.removeEventListener("keydown", containDialogFocus);
      previouslyFocused?.focus();
    };
  }, [open]);

  // OPTIMISTIC UI — cập nhật ngay khi bấm (khỏi chờ refetch cả trang cho mượt).
  //   overrides: ghi đè trạng thái theo id ("REMOVED" = ẩn ca).
  //   optimistic: ca vừa đăng ký, chưa kịp về từ server.
  // Khi data server mới phản ánh đúng thay đổi → tự bỏ override/optimistic tương ứng.
  const [overrides, setOverrides] = useState<
    Record<string, "APPROVED" | "REJECTED" | "REMOVED">
  >({});
  const [optimistic, setOptimistic] = useState<RegisterRow[]>([]);

  const refresh = () => startTransition(() => router.refresh());

  // Danh sách hiệu lực = data server + áp optimistic (TÍNH KHI RENDER, không dùng
  // effect): ẩn ca REMOVED, đổi trạng thái theo override, thêm ca vừa đăng ký nếu
  // server chưa trả về (dedupe theo người+ngày+trạm để không trùng sau khi refetch).
  const effRows: RegisterRow[] = [
    ...rows
      .filter((r) => overrides[r.id] !== "REMOVED")
      .map((r) =>
        overrides[r.id]
          ? { ...r, status: overrides[r.id] as RegisterRow["status"] }
          : r,
      ),
    ...optimistic.filter(
      (o) =>
        !rows.some(
          (r) =>
            r.staff_id === o.staff_id &&
            r.work_date === o.work_date &&
            r.station === o.station,
        ),
    ),
  ];

  async function decide(id: string, action: "approve" | "reject", reasonText?: string) {
    setError(null);
    setOverrides((ov) => ({
      ...ov,
      [id]: action === "approve" ? "APPROVED" : "REJECTED",
    }));
    setRejectingId(null);
    setReason("");
    const res = await fetch("/api/roster", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, action, reason: reasonText }),
    });
    if (!res.ok) {
      setOverrides((ov) => {
        const n = { ...ov };
        delete n[id];
        return n;
      });
      setError((await res.json()).error ?? "Lỗi khi duyệt.");
      return;
    }
    refresh();
  }

  // byCell[date|station] = các đăng ký ở ô đó (mọi người, mọi trạng thái).
  const byCell = new Map<string, RegisterRow[]>();
  for (const r of effRows) {
    const k = cellKey(r.work_date, r.station);
    const list = byCell.get(k) ?? [];
    list.push(r);
    byCell.set(k, list);
  }

  const openCellRows = open ? byCell.get(cellKey(open.date, open.station)) ?? [] : [];
  // "Đã đăng ký" chỉ tính ca ĐANG hiệu lực (Chờ duyệt / Đã duyệt) của mình. Ca bị
  // TỪ CHỐI không tính → cho phép đăng ký lại ô đó.
  const myHere = openCellRows.find(
    (r) => r.staff_id === myStaffId && r.status !== "REJECTED",
  );

  async function register() {
    if (!open) return;
    const { date, station } = open;
    setError(null);
    const tempId = `temp-${date}-${station}-${shift}`;
    setOptimistic((opt) => [
      ...opt,
      {
        id: tempId,
        work_date: date,
        station,
        shift,
        staff_id: myStaffId,
        staff_name: myStaffName ?? "Tôi",
        status: "PENDING",
        reject_reason: null,
      },
    ]);
    setOpen(null);
    const res = await fetch("/api/roster", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ week_start: weekStart, work_date: date, station, shift }),
    });
    if (!res.ok) {
      setOptimistic((opt) => opt.filter((o) => o.id !== tempId));
      setError((await res.json()).error ?? "Lỗi khi đăng ký.");
      setOpen({ date, station });
      return;
    }
    refresh();
  }

  async function remove(id: string) {
    setError(null);
    setOverrides((ov) => ({ ...ov, [id]: "REMOVED" }));
    setOpen(null);
    const res = await fetch("/api/roster", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });
    if (!res.ok) {
      setOverrides((ov) => {
        const n = { ...ov };
        delete n[id];
        return n;
      });
      setError((await res.json()).error ?? "Lỗi khi xoá.");
      return;
    }
    refresh();
  }

  return (
    <>
      <div className="max-h-[88vh] min-h-[180px] max-w-full overflow-auto rounded-card border border-line bg-surface shadow-card">
        <table className="w-full min-w-max border-collapse text-xs">
          <thead>
            <tr className="bg-brand-100">
              <th
                rowSpan={2}
                className="sticky left-0 z-20 border-b border-r border-brand-100 bg-brand-100 px-2 py-2 text-left font-semibold text-brand-800"
              >
                Ngày
              </th>
              {STATION_SEGMENTS.map((seg) =>
                seg.floor === "" ? (
                  seg.stations.map((s) => (
                    <th key={s.key} rowSpan={2} className={`min-w-[110px] ${TH_BASE}`}>
                      {s.short}
                    </th>
                  ))
                ) : (
                  <th
                    key={seg.floor}
                    colSpan={seg.stations.length}
                    className={`${TH_BASE} border-t-2 border-t-brand-400`}
                  >
                    {seg.floor}
                  </th>
                ),
              )}
            </tr>
            <tr className="bg-brand-50">
              {STATIONS.filter((s) => s.floor !== "").map((s) => (
                <th
                  key={s.key}
                  className="min-w-[104px] border-b border-r border-brand-100 px-2 py-1.5 text-center font-medium text-brand-700"
                >
                  {s.short}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {dates.map((d, ri) => (
              <tr key={d} className={"align-top " + (ri % 2 ? "bg-brand-50" : "bg-surface")}>
                <td className="sticky left-0 z-10 whitespace-nowrap border-b border-r border-brand-100 bg-inherit px-2 py-2 font-medium text-ink">
                  {dayShort(d)} · {fmtDayMonth(d)}
                </td>
                {STATIONS.map((s) => {
                  const list = byCell.get(cellKey(d, s.key)) ?? [];
                  return (
                    <td
                      key={s.key}
                      className="border-b border-r border-brand-100 p-0"
                    >
                      <button
                        type="button"
                        onClick={() => {
                          setError(null);
                          setShift("FULL");
                          setRejectingId(null);
                          setReason("");
                          setOpen({ date: d, station: s.key });
                        }}
                        className="flex h-full min-h-[40px] w-full flex-col gap-0.5 px-1.5 py-1.5 text-center transition-colors hover:bg-brand-50"
                      >
                        {list.length === 0 ? (
                          <span className="text-brand-200">+</span>
                        ) : (
                          list.map((r) => {
                            const b = STATUS_BADGE[r.status];
                            return (
                              <span
                                key={r.id}
                                className={
                                  "block whitespace-nowrap rounded px-1 leading-snug " +
                                  b.cls +
                                  (r.status === "REJECTED" ? " line-through" : "") +
                                  (r.staff_id === myStaffId ? " ring-1 ring-brand-600/40" : "")
                                }
                                title={`${b.label}${r.reject_reason ? " — " + r.reject_reason : ""}`}
                              >
                                {r.staff_name}
                                {r.shift !== "FULL" ? ` (${SHIFT_LABEL[r.shift]})` : ""}
                              </span>
                            );
                          })
                        )}
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Modal "nảy ra" khi click 1 ô */}
      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 p-4"
          onClick={() => setOpen(null)}
        >
          <div
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby={dialogTitleId}
            className="max-h-[calc(100dvh-2rem)] w-full max-w-md overflow-y-auto rounded-card border border-line bg-surface p-4 shadow-panel"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-3 flex items-start justify-between gap-2">
              <h3 id={dialogTitleId} className="text-sm font-semibold text-ink">
                Đăng ký ca · {dayShort(open.date)} {fmtDayMonth(open.date)}
                <span className="block text-xs font-normal text-ink-muted">
                  {STATION_LABEL[open.station] ?? open.station}
                </span>
              </h3>
              <button
                onClick={() => setOpen(null)}
                aria-label="Đóng"
                autoFocus
                className="rounded-md p-1 text-ink-faint hover:bg-surface-sunken"
              >
                <X size={16} />
              </button>
            </div>

            {/* Ai đã đăng ký ô này (để biết lịch dự kiến của người khác). */}
            {openCellRows.length > 0 && (
              <div className="mb-3 rounded-lg border border-surface-sunken bg-surface-muted p-2">
                <p className="mb-1 text-xs font-medium text-ink-muted">
                  Đã đăng ký ô này
                </p>
                <ul className="space-y-1">
                  {openCellRows.map((r) => {
                    const b = STATUS_BADGE[r.status];
                    return (
                      <li key={r.id} className="text-xs text-ink-soft">
                        <div className="flex items-center justify-between gap-2">
                          <span className="min-w-0">
                            <span className="font-medium text-ink">
                              {r.staff_name}
                            </span>
                            {r.shift !== "FULL" && (
                              <span className="text-ink-faint">
                                {" "}
                                ({SHIFT_LABEL[r.shift]})
                              </span>
                            )}
                            <span
                              className={"ml-1.5 rounded px-1.5 py-0.5 font-medium " + b.cls}
                            >
                              {b.label}
                            </span>
                            {r.status === "REJECTED" && r.reject_reason && (
                              <span className="block text-danger">
                                Lý do: {r.reject_reason}
                              </span>
                            )}
                          </span>
                          {r.staff_id === myStaffId && r.status === "PENDING" && (
                            <button
                              onClick={() => remove(r.id)}
                              aria-label="Xoá ca của tôi"
                              className="shrink-0 rounded p-1 text-ink-faint hover:bg-danger-bg hover:text-danger disabled:opacity-50"
                            >
                              <Trash2 size={14} />
                            </button>
                          )}
                        </div>

                        {/* Quản lý: Duyệt / Từ chối ngay tại đây cho ca chờ duyệt. */}
                        {isApprover && r.status === "PENDING" && (
                          <div className="mt-1.5">
                            {rejectingId === r.id ? (
                              <div className="rounded-control border border-warning bg-warning-bg p-2">
                                <textarea
                                  value={reason}
                                  onChange={(e) => setReason(e.target.value)}
                                  rows={2}
                                  autoFocus
                                  placeholder="Lý do từ chối (gửi cho người đăng ký)…"
                                  className="w-full resize-none rounded-control border border-line bg-surface px-2.5 py-1.5 text-xs focus:border-brand-600 focus:outline-none"
                                />
                                <div className="mt-1.5 flex justify-end gap-1.5">
                                  <button
                                    onClick={() => {
                                      setRejectingId(null);
                                      setReason("");
                                    }}
                                    className="rounded-control border border-line bg-surface px-2.5 py-1 text-xs text-ink-soft hover:bg-surface-sunken"
                                  >
                                    Huỷ
                                  </button>
                                  <button
                                    onClick={() => decide(r.id, "reject", reason)}
                                    disabled={!reason.trim()}
                                    className="rounded-control bg-danger px-2.5 py-1 text-xs font-medium text-surface disabled:opacity-50"
                                  >
                                    Xác nhận từ chối
                                  </button>
                                </div>
                              </div>
                            ) : (
                              <div className="flex gap-1.5">
                                <button
                                  onClick={() => decide(r.id, "approve")}
                                  className="flex items-center gap-1 rounded-control bg-success px-2.5 py-1 text-xs font-medium text-surface disabled:opacity-50"
                                >
                                  <Check size={13} /> Duyệt
                                </button>
                                <button
                                  onClick={() => {
                                    setError(null);
                                    setReason("");
                                    setRejectingId(r.id);
                                  }}
                                  className="flex items-center gap-1 rounded-control border border-line bg-surface px-2.5 py-1 text-xs font-medium text-danger hover:bg-danger-bg disabled:opacity-50"
                                >
                                  <X size={13} /> Từ chối
                                </button>
                              </div>
                            )}
                          </div>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}

            {error && (
              <p className="mb-2 rounded bg-danger-bg px-3 py-2 text-sm text-danger">
                {error}
              </p>
            )}

            {isApprover && openCellRows.length === 0 && (
              <p className="rounded bg-surface-muted px-3 py-2 text-sm text-ink-muted">
                Chưa có ai đăng ký ô này.
              </p>
            )}

            {/* Form tự đăng ký — CHỈ cho nhân viên trực ca. Quản lý hệ thống mở
                popup chỉ để duyệt/từ chối, không tự đăng ký ca → ẩn phần này. */}
            {!isApprover && (
              <>
            {myStaffId == null ? (
              <p className="rounded-control bg-warning-bg px-3 py-2 text-sm text-warning">
                Chưa chọn danh tính nhân viên — không thể tự đăng ký ca.
              </p>
            ) : myHere ? (
              <p className="rounded-control bg-status-in-progress-bg px-3 py-2 text-sm text-status-in-progress">
                Bạn đã đăng ký ô này
                {myHere.status === "PENDING"
                  ? " — đang chờ quản lý duyệt."
                  : " và đã được duyệt."}
              </p>
            ) : (
              <div className="flex items-end gap-2">
                <div className="flex-1">
                  <label className="mb-1 block text-xs font-medium text-ink-muted">
                    Ca
                  </label>
                  <select
                    className="w-full rounded-control border border-line bg-surface px-3 py-2 text-sm focus:border-brand-600 focus:outline-none"
                    value={shift}
                    onChange={(e) => setShift(e.target.value as Shift)}
                  >
                    {SHIFTS.map((s) => (
                      <option key={s} value={s}>
                        {SHIFT_LABEL[s]}
                      </option>
                    ))}
                  </select>
                </div>
                <button
                  onClick={register}
                  className="rounded-control bg-brand-600 px-4 py-2 text-sm font-medium text-surface hover:bg-brand-700"
                >
                  Đăng ký
                </button>
              </div>
            )}
            <p className="mt-3 text-xs text-ink-faint">
              Ca đăng ký sẽ ở trạng thái “Chờ duyệt” đến khi quản lý xác nhận.
            </p>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}
