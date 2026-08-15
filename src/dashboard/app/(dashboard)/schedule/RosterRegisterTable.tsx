"use client";

// "Đăng ký / xếp ca" — bảng MA TRẬN tương tác (ngày × trạm, gom theo tầng, mỗi
// ngày HAI HÀNG CON), CÙNG layout với hai bảng chỉ-đọc ở trên. Khác ở chỗ:
//   - Click 1 ô → popup: quản lý CHỌN NGƯỜI + chọn ca rồi xếp vào đúng trạm +
//     đúng ngày; nhân viên (nếu về sau mở lại) chỉ tự đăng ký ca của mình.
//   - Ô trống có dấu "+"; ô đã có người hiện tên + ca.
// Ghi qua /api/roster (POST xếp, DELETE gỡ) rồi router.refresh().

import { useEffect, useId, useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { X, Trash2 } from "lucide-react";
import {
  STATION_LABEL,
  SHIFTS,
  SHIFT_LABEL,
  chiaHaiHang,
  demBacSiTruc,
  dayShort,
  fmtDayMonth,
  type Shift,
} from "../../../lib/roster";
import { RosterGridHead, RosterDayRows, O_TREN, O_DUOI } from "../RosterGrid";
import { loiDocDuoc } from "../../../lib/loi-doc-duoc";

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

/** Một người có thể xếp được, kèm chức danh để lọc theo phạm vi trạm. */
export interface StaffOpt {
  id: string;
  name: string;
  /** `staff.primary_department` — khoá của ma trận `vai_duoc_vao_tram`. */
  vai: string;
}

// KHÔNG CÒN "CHỜ DUYỆT" (Quang 09/08/2026: *"cần gì phải duyệt với không
// duyệt, chỉ có quản lý toàn quyền mà"*).
//
// Bảng này giờ CHỈ quản lý thấy, và backend đã ghi thẳng APPROVED cho quản lý
// (config_service.py: `"APPROVED" if is_admin else "PENDING"`). Nên mọi ô ở đây
// vốn đã là ca chính thức — dán thêm nhãn "Đã duyệt" lên từng dòng là bày ra
// một quy trình không tồn tại, và bắt người đọc phân biệt hai trạng thái mà
// thực tế chỉ có một.
//
// Ca REJECTED cũ vẫn còn trong database (từ thời có luồng duyệt) nên vẫn phải
// vẽ khác đi — gạch ngang, mờ — chứ không lẫn vào ca đang có hiệu lực.
const STATUS_BADGE: Record<RegisterRow["status"], { cls: string; label: string }> = {
  PENDING: { cls: "bg-brand-50 text-brand-800", label: "Đã xếp" },
  APPROVED: { cls: "bg-brand-50 text-brand-800", label: "Đã xếp" },
  REJECTED: { cls: "bg-surface-sunken text-ink-faint", label: "Đã gỡ" },
};

function cellKey(date: string, station: string) {
  return `${date}|${station}`;
}

export default function RosterRegisterTable({
  weekStart,
  dates,
  rows,
  myStaffId,
  myStaffName,
  staff = [],
  tramTheoVai = {},
  isApprover = false,
}: {
  weekStart: string;
  dates: string[];
  rows: RegisterRow[];
  /** staff_id người đang đăng nhập; null = chưa chọn danh tính (không đăng ký được). */
  myStaffId: string | null;
  /** Tên người đăng nhập — hiện ngay cho ca vừa đăng ký (optimistic). */
  myStaffName?: string;
  /** Danh sách nhân viên để quản lý chọn xếp vào ô. */
  staff?: StaffOpt[];
  /** Chức danh → những mã trạm được xếp vào (bảng `vai_duoc_vao_tram`). */
  tramTheoVai?: Record<string, string[]>;
  /** Quản lý hệ thống: được chọn NGƯỜI để xếp, và gỡ được ca của bất kỳ ai. */
  isApprover?: boolean;
}) {
  const router = useRouter();
  const dialogTitleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState<{ date: string; station: string } | null>(null);
  const [shift, setShift] = useState<Shift>("FULL");
  const [pickedId, setPickedId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
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
  //   optimistic: ca vừa xếp, chưa kịp về từ server.
  // Khi data server mới phản ánh đúng thay đổi → tự bỏ override/optimistic tương ứng.
  const [overrides, setOverrides] = useState<
    Record<string, "APPROVED" | "REJECTED" | "REMOVED">
  >({});
  const [optimistic, setOptimistic] = useState<RegisterRow[]>([]);

  const refresh = () => startTransition(() => router.refresh());

  // Danh sách hiệu lực = data server + áp optimistic (TÍNH KHI RENDER, không dùng
  // effect): ẩn ca REMOVED, đổi trạng thái theo override, thêm ca vừa xếp nếu
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

  // byCell[date|station] = các ca ở ô đó (mọi người, mọi trạng thái).
  const byCell = new Map<string, RegisterRow[]>();
  for (const r of effRows) {
    const k = cellKey(r.work_date, r.station);
    const list = byCell.get(k) ?? [];
    list.push(r);
    byCell.set(k, list);
  }

  const openCellRows = open ? byCell.get(cellKey(open.date, open.station)) ?? [] : [];
  // "Đã đăng ký" chỉ tính ca ĐANG hiệu lực (Đã xếp) của mình. Ca bị gỡ không
  // tính → cho phép xếp lại ô đó.
  const myHere = openCellRows.find(
    (r) => r.staff_id === myStaffId && r.status !== "REJECTED",
  );

  // AI ĐƯỢC XẾP VÀO Ô NÀY — lọc bằng ĐÚNG ma trận mà backend dùng để từ chối
  // (`vai_duoc_vao_tram`, xem RosterService._kiem_pham_vi_tram). Hỏi hai nguồn
  // là sớm muộn popup mời một người mà lúc lưu mới báo lỗi.
  //
  // Chức danh CHƯA KHAI dòng nào → cho qua, y như backend: phòng khám mới cài
  // đặt chưa có ma trận, chặn hết ở đây là màn xếp lịch chết câm ngày đầu.
  const daCoTrongO = new Set(
    openCellRows.filter((r) => r.status !== "REJECTED").map((r) => r.staff_id),
  );
  const nhanVienHopLe = open
    ? staff.filter((s) => {
        if (daCoTrongO.has(s.id)) return false;
        const tram = tramTheoVai[s.vai];
        return !tram || tram.length === 0 || tram.includes(open.station);
      })
    : [];

  function moO(date: string, station: string) {
    setError(null);
    setShift("FULL");
    setPickedId("");
    setOpen({ date, station });
  }

  /** Quản lý xếp NGƯỜI ĐƯỢC CHỌN; vai khác tự đăng ký chính mình. */
  async function xepCa() {
    if (!open) return;
    const { date, station } = open;
    const picked = isApprover ? staff.find((s) => s.id === pickedId) : null;
    if (isApprover && !picked) {
      setError("Chọn nhân viên trước đã.");
      return;
    }
    setError(null);
    setBusy(true);
    const tempId = `temp-${date}-${station}-${picked?.id ?? myStaffId}-${shift}`;
    setOptimistic((opt) => [
      ...opt,
      {
        id: tempId,
        work_date: date,
        station,
        shift,
        staff_id: picked?.id ?? myStaffId,
        staff_name: picked?.name ?? myStaffName ?? "Tôi",
        // Quản lý xếp → backend ghi thẳng APPROVED. Vẽ optimistic là PENDING thì
        // ô nhấp nháy đổi nhãn khi server trả về.
        status: isApprover ? "APPROVED" : "PENDING",
        reject_reason: null,
      },
    ]);
    const res = await fetch("/api/roster", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        week_start: weekStart,
        work_date: date,
        station,
        shift,
        staff_id: picked?.id ?? null,
        staff_name: picked?.name ?? null,
        // Người xếp sau nằm ở hàng con dưới. Không gửi thì mọi dòng cùng sort=0
        // và thứ tự hai hàng đảo qua đảo lại giữa các lần tải trang.
        sort: openCellRows.length,
      }),
    });
    setBusy(false);
    const than = await res.json().catch(() => ({}));
    if (!res.ok) {
      setOptimistic((opt) => opt.filter((o) => o.id !== tempId));
      setError(loiDocDuoc(than, "Lỗi khi xếp ca."));
      return;
    }
    // ĐỔI ID TẠM SANG ID THẬT NGAY KHI SERVER TRẢ VỀ.
    //
    // Bản trước để nguyên dòng optimistic mang `temp-…` rồi chỉ gọi refresh().
    // Nhưng popup CỐ Ý ở lại mở, nên người xếp xong thấy ngay dòng vừa thêm —
    // và dòng ấy vẫn là dòng tạm. Bấm thùng rác trên nó gửi
    // `DELETE /roster/shifts/temp-2026-08-22-LICH_KHAM-…` xuống máy chủ; đường
    // ấy khai tham số là UUID nên trả 422, và màn hình chỉ nói "Lỗi khi gỡ ca."
    //
    // Đo trên prod 14/08/2026: id thật gỡ được (200), id tạm 422 ba lần liên
    // tiếp — Tuyền bấm lại ba lần vì không có gì nói cho biết vì sao.
    //
    // Không xoá hẳn dòng tạm ở đây: refresh() là một vòng mạng nữa, và trong
    // lúc chờ thì ô vừa xếp trống trở lại rồi mới hiện — nhấp nháy đúng vào
    // khoảnh khắc người ta đang nhìn nó.
    const idThat = typeof than?.id === "string" ? than.id : null;
    setOptimistic((opt) =>
      idThat
        ? opt.map((o) => (o.id === tempId ? { ...o, id: idThat } : o))
        : opt.filter((o) => o.id !== tempId),
    );
    // GIỮ POPUP MỞ. Mỗi ngày có tới hai người mỗi trạm; đóng lại sau người thứ
    // nhất là bắt quản lý bấm vào đúng ô ấy thêm một lần nữa.
    setPickedId("");
    refresh();
  }

  async function remove(id: string) {
    setError(null);
    // CHỐT CUỐI: không bao giờ gửi một id tạm xuống máy chủ. Trên lý thuyết
    // xepCa() đã đổi nó sang id thật rồi, nhưng nếu vòng mạng ấy hỏng thì dòng
    // tạm vẫn còn — và khi đó câu trả lời đúng là "làm mới rồi thử lại", không
    // phải một mã 422 khó hiểu.
    if (id.startsWith("temp-")) {
      setError("Ca này chưa lưu xong. Bấm làm mới rồi gỡ lại.");
      refresh();
      return;
    }
    setOverrides((ov) => ({ ...ov, [id]: "REMOVED" }));
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
      setError(loiDocDuoc(await res.json().catch(() => ({})), "Lỗi khi gỡ ca."));
      return;
    }
    refresh();
  }

  return (
    <>
      <div className="max-h-[88vh] min-h-[180px] max-w-full overflow-auto rounded-card border border-line bg-surface shadow-card">
        <table className="w-full min-w-max border-collapse text-xs">
          <RosterGridHead minWidth={104} />
          <tbody>
            {dates.map((d, ri) => (
              <RosterDayRows
                key={d}
                nhan={`${dayShort(d)} · ${fmtDayMonth(d)}`}
                soBacSi={demBacSiTruc(
                  effRows.filter((r) => r.status !== "REJECTED"),
                  d,
                )}
                vach={ri % 2 ? "bg-surface-muted" : "bg-surface"}
                oCua={(s, hang) => {
                  const list = chiaHaiHang(byCell.get(cellKey(d, s.key)) ?? [])[hang];
                  return (
                    <td className={(hang === 0 ? O_TREN : O_DUOI) + " p-0"}>
                      <button
                        type="button"
                        onClick={() => moO(d, s.key)}
                        className="flex h-full min-h-[30px] w-full flex-col gap-0.5 px-1.5 py-1 text-center transition-colors hover:bg-brand-50"
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
                }}
              />
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
                {isApprover ? "Xếp ca" : "Đăng ký ca"} · {dayShort(open.date)}{" "}
                {fmtDayMonth(open.date)}
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

            {/* Ai đang ở ô này (để thấy lịch của người khác trước khi xếp thêm). */}
            {openCellRows.length > 0 && (
              <div className="mb-3 rounded-lg border border-surface-sunken bg-surface-muted p-2">
                <p className="mb-1 text-xs font-medium text-ink-muted">
                  Đang xếp ở ô này
                </p>
                <ul className="space-y-1">
                  {openCellRows.map((r) => {
                    const b = STATUS_BADGE[r.status];
                    // Quản lý gỡ được ca của BẤT KỲ AI — đúng luật của
                    // RosterService.remove. Người thường chỉ gỡ ca của mình.
                    const goDuoc = isApprover || r.staff_id === myStaffId;
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
                          {goDuoc && (
                            <button
                              onClick={() => remove(r.id)}
                              aria-label={`Gỡ ${r.staff_name} khỏi ca này`}
                              className="shrink-0 rounded p-1 text-ink-faint hover:bg-danger-bg hover:text-danger disabled:opacity-50"
                            >
                              <Trash2 size={14} />
                            </button>
                          )}
                        </div>
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

            {/* QUẢN LÝ: chọn người + chọn ca rồi xếp.

                Khối này TỪNG KHÔNG TỒN TẠI. Sau khi bỏ trang /schedule/edit
                (09/08), popup chỉ hiện đúng câu "Chưa có ai đăng ký ô này" cho
                quản lý — tức là dấu "+" mở ra một ngõ cụt và cả phòng khám không
                còn đường nào xếp lịch trực. */}
            {isApprover ? (
              <div className="space-y-2">
                <div>
                  <label
                    htmlFor={`${dialogTitleId}-nv`}
                    className="mb-1 block text-xs font-medium text-ink-muted"
                  >
                    Nhân viên
                  </label>
                  <select
                    id={`${dialogTitleId}-nv`}
                    className="w-full rounded-control border border-line bg-surface px-3 py-2 text-sm focus:border-brand-600 focus:outline-none"
                    value={pickedId}
                    onChange={(e) => {
                      setPickedId(e.target.value);
                      setError(null);
                    }}
                  >
                    <option value="">— Chọn người —</option>
                    {nhanVienHopLe.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                  </select>
                  {nhanVienHopLe.length === 0 && (
                    <p className="mt-1 text-xs text-ink-faint">
                      Không còn ai được xếp vào vị trí này. Phạm vi vị trí theo
                      chức danh nằm ở bảng “Ai được vào vị trí nào”.
                    </p>
                  )}
                </div>
                <div className="flex items-end gap-2">
                  <div className="flex-1">
                    <label
                      htmlFor={`${dialogTitleId}-ca`}
                      className="mb-1 block text-xs font-medium text-ink-muted"
                    >
                      Ca
                    </label>
                    <select
                      id={`${dialogTitleId}-ca`}
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
                    onClick={xepCa}
                    disabled={busy || !pickedId}
                    className="rounded-control bg-brand-600 px-4 py-2 text-sm font-medium text-surface hover:bg-brand-700 disabled:opacity-50"
                  >
                    Xếp vào
                  </button>
                </div>
                <p className="text-xs text-ink-faint">
                  Xếp xong ca vào thẳng lịch chính thức. Popup vẫn mở để xếp tiếp
                  người thứ hai của ô này.
                </p>
              </div>
            ) : myStaffId == null ? (
              <p className="rounded-control bg-warning-bg px-3 py-2 text-sm text-warning">
                Chưa chọn danh tính nhân viên — không thể tự đăng ký ca.
              </p>
            ) : myHere ? (
              <p className="rounded-control bg-status-in-progress-bg px-3 py-2 text-sm text-status-in-progress">
                Bạn đã đăng ký ô này.
              </p>
            ) : (
              <div className="flex items-end gap-2">
                <div className="flex-1">
                  <label
                    htmlFor={`${dialogTitleId}-ca-toi`}
                    className="mb-1 block text-xs font-medium text-ink-muted"
                  >
                    Ca
                  </label>
                  <select
                    id={`${dialogTitleId}-ca-toi`}
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
                  onClick={xepCa}
                  disabled={busy}
                  className="rounded-control bg-brand-600 px-4 py-2 text-sm font-medium text-surface hover:bg-brand-700 disabled:opacity-50"
                >
                  Đăng ký
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
