"use client";

// "Công việc của tôi" của vai THU NGÂN — màn THU TIỀN theo buổi khám (T-DASH-CASHIER-PAY-01).
// TRÁI: danh sách BN đang khám hôm nay (ô gộp: tên + mã + SĐT). PHẢI: khoản thu
//   • Dịch vụ  → service_log của BN hôm nay (ĐỒNG BỘ thật).
//   • Thuốc    → prescription của lượt khám (ĐỒNG BỘ thật).
// Nút "Thanh toán" → hiện khu mã QR (PLACEHOLDER, chưa nối cổng) → "Đã thanh toán".
// Payment được lưu ở backend; hoàn tác luôn cần lý do để giữ audit tài chính.
// Giá lấy best-effort từ service_price (khớp tên); chưa có → để trống.

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { QrCode, Check, CheckCircle2, RotateCcw, Pill, Tag } from "lucide-react";
import { calculateCashierTotal } from "@/lib/cashier-total";

export type CashierMode = "thuoc" | "dich_vu";

export interface CashierServiceItem {
  id: string;
  name: string;
  price: number | null;
}
export interface CashierDrugItem {
  id: string;
  name: string;
  quantity: string | null;
  dosage: string | null;
  price: number | null;
}
export interface CashierRow {
  visit_id: string;
  clinic_patient_id: string;
  full_name: string | null;
  patient_code: string | null;
  phone: string | null;
  appt_status: string | null;
  services: CashierServiceItem[];
  drugs: CashierDrugItem[];
}

const MODE_META: Record<
  CashierMode,
  { label: string; payLabel: string; icon: typeof Pill }
> = {
  thuoc: { label: "Thu ngân thuốc", payLabel: "Thanh toán thuốc", icon: Pill },
  dich_vu: { label: "Thu ngân dịch vụ", payLabel: "Thanh toán dịch vụ", icon: Tag },
};

function fmtVnd(v: number | null): string {
  if (v === null) return "—";
  return new Intl.NumberFormat("vi-VN").format(v) + " ₫";
}

const TH =
  "border-b border-surface-sunken px-4 py-2.5 text-left font-semibold text-[#525252]";
const TD = "border-b border-[#f3f3f3] px-4 py-3 align-top text-ink";

export default function CashierWorkBoard({
  rows,
  modes,
  paidInit = [],
}: {
  rows: CashierRow[];
  /** Vai quyết định mode được thấy: CASHIER_THUOC=[thuoc], CASHIER_DV=[dich_vu],
   *  CASHIER=[thuoc,dich_vu] (toggle). */
  modes: CashierMode[];
  /** Dòng payment ĐÃ THU (từ bảng payment) — seed trạng thái để giữ qua tải lại. */
  paidInit?: { visit_id: string; kind: CashierMode }[];
}) {
  const router = useRouter();
  const [mode, setMode] = useState<CashierMode>(modes[0] ?? "dich_vu");
  // BN đang mở khu QR (key = `${mode}:${visit_id}`). 1 khu mở 1 lúc.
  const [payOpen, setPayOpen] = useState<string | null>(null);
  // "Đã thanh toán" — seed từ bảng payment, giữ qua tải lại + đồng bộ 2 màn / Lễ tân.
  const [paid, setPaid] = useState<Set<string>>(
    () => new Set(paidInit.map((p) => `${p.kind}:${p.visit_id}`)),
  );
  const [busy, setBusy] = useState<string | null>(null); // key đang gọi API
  const [err, setErr] = useState<string | null>(null);
  const [voidOpen, setVoidOpen] = useState<string | null>(null);
  const [voidReason, setVoidReason] = useState("");

  const meta = MODE_META[mode];
  const key = (visitId: string) => `${mode}:${visitId}`;

  // Lưu THẬT qua backend rồi cập nhật state + refresh để màn
  // Lễ tân (thanh tiến trình) đồng bộ qua realtime.
  async function togglePaid(r: CashierRow, reversalReason?: string) {
    const k = key(r.visit_id);
    const isPaid = paid.has(k);
    const normalizedReason = reversalReason?.trim();
    const { sum, missing } = calculateCashierTotal(mode, r.services, r.drugs);
    if (
      isPaid &&
      (!normalizedReason ||
        normalizedReason.length < 5 ||
        normalizedReason.length > 500)
    ) {
      setErr("Lý do hoàn tác phải có từ 5 đến 500 ký tự.");
      return;
    }
    if (!isPaid && (missing || sum <= 0)) {
      setErr(
        "Chưa thể thu tiền khi còn khoản chưa có giá hoặc số lượng thuốc chưa hợp lệ.",
      );
      return;
    }

    setBusy(k);
    setErr(null);
    try {
      const res = await fetch("/api/payment", {
        method: isPaid ? "DELETE" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          isPaid
            ? { visitId: r.visit_id, kind: mode, reason: normalizedReason }
            : {
                visitId: r.visit_id,
                clinicPatientId: r.clinic_patient_id,
                kind: mode,
                amount: sum,
              },
        ),
      });
      if (!res.ok) {
        setErr((await res.json().catch(() => ({})))?.error ?? "Lỗi thanh toán.");
        return;
      }
      setPaid((current) => {
        const next = new Set(current);
        if (isPaid) next.delete(k);
        else next.add(k);
        return next;
      });
      setPayOpen(null);
      setVoidOpen(null);
      setVoidReason("");
      router.refresh();
    } catch {
      setErr("Không kết nối được máy chủ thanh toán. Vui lòng thử lại.");
    } finally {
      setBusy(null);
    }
  }

  const hasItems = (r: CashierRow) =>
    mode === "thuoc" ? r.drugs.length > 0 : r.services.length > 0;

  const shown = useMemo(() => rows, [rows]);

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold text-ink">Công việc của tôi</h1>
        <p className="text-sm text-ink-muted">
          Thu tiền theo buổi khám hôm nay. Dịch vụ &amp; thuốc lấy thật từ hồ sơ khám.
          Trạng thái “Đã thanh toán” được LƯU &amp; đồng bộ với thanh tiến trình bên
          Lễ tân. Mã QR là placeholder (chưa nối cổng thanh toán thật).
        </p>
      </header>

      {err && (
        <p className="rounded bg-danger-bg px-3 py-2 text-sm text-danger">{err}</p>
      )}

      {/* Toggle 2 mode — chỉ khi vai thấy cả hai (CASHIER superset). */}
      {modes.length > 1 && (
        <div className="inline-flex rounded-xl border border-line bg-white p-1 shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
          {modes.map((m) => (
            <button
              key={m}
              onClick={() => {
                setMode(m);
                setPayOpen(null);
                setVoidOpen(null);
                setVoidReason("");
              }}
              className={
                "rounded-lg px-4 py-1.5 text-sm font-medium transition-colors " +
                (mode === m
                  ? "bg-brand-600 text-white"
                  : "text-ink-soft hover:bg-brand-50")
              }
            >
              {MODE_META[m].label}
            </button>
          ))}
        </div>
      )}

      <div className="overflow-auto rounded-xl border border-surface-sunken bg-white shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
        <table className="w-full min-w-max border-collapse text-sm">
          <thead className="bg-surface-muted">
            <tr>
              <th className={`${TH} min-w-[220px]`}>Bệnh nhân</th>
              <th className={`${TH} min-w-[360px]`}>{meta.payLabel}</th>
            </tr>
          </thead>
          <tbody>
            {shown.length === 0 ? (
              <tr>
                <td className="px-4 py-6 text-center text-ink-muted" colSpan={2}>
                  Chưa có bệnh nhân đang khám hôm nay.
                </td>
              </tr>
            ) : (
              shown.map((r) => {
                const k = key(r.visit_id);
                const isPaid = paid.has(k);
                const open = payOpen === k;
                const { sum, missing } = calculateCashierTotal(
                  mode,
                  r.services,
                  r.drugs,
                );
                return (
                  <tr key={r.visit_id} className="hover:bg-surface-muted">
                    {/* Ô 1 — BN gộp: tên + mã + SĐT. */}
                    <td className={TD}>
                      <div className="font-semibold text-ink">
                        {r.full_name ?? "—"}
                      </div>
                      <div className="mt-0.5 font-mono text-xs text-ink-muted">
                        {r.patient_code ?? "—"}
                      </div>
                      <div className="text-xs text-ink-muted">
                        {r.phone ?? "—"}
                      </div>
                    </td>

                    {/* Ô 2 — khoản thu (dịch vụ/thuốc) + nút Thanh toán → QR. */}
                    <td className={TD}>
                      {!hasItems(r) ? (
                        <span className="text-sm text-ink-faint">
                          — chưa có {mode === "thuoc" ? "thuốc" : "dịch vụ"} —
                        </span>
                      ) : (
                        <div className="space-y-2">
                          <ul className="divide-y divide-surface-sunken rounded-lg border border-[#eee]">
                            {mode === "dich_vu"
                              ? r.services.map((s) => (
                                  <li
                                    key={s.id}
                                    className="flex items-center justify-between gap-3 px-3 py-1.5"
                                  >
                                    <span className="min-w-0 truncate text-ink">
                                      {s.name}
                                    </span>
                                    <span className="shrink-0 tabular-nums text-ink-soft">
                                      {fmtVnd(s.price)}
                                    </span>
                                  </li>
                                ))
                              : r.drugs.map((d) => (
                                  <li
                                    key={d.id}
                                    className="flex items-center justify-between gap-3 px-3 py-1.5"
                                  >
                                    <span className="min-w-0">
                                      <span className="text-ink">{d.name}</span>
                                      {(d.quantity || d.dosage) && (
                                        <span className="ml-1 text-xs text-ink-muted">
                                          {[d.quantity, d.dosage]
                                            .filter(Boolean)
                                            .join(" · ")}
                                        </span>
                                      )}
                                    </span>
                                    <span className="shrink-0 tabular-nums text-ink-soft">
                                      {fmtVnd(d.price)}
                                    </span>
                                  </li>
                                ))}
                          </ul>

                          <div className="flex items-center justify-between gap-2 text-sm">
                            <span className="text-ink-muted">
                              Tạm tính:{" "}
                              <span className="font-semibold text-ink tabular-nums">
                                {fmtVnd(sum)}
                              </span>
                              {missing && (
                                <span className="ml-1 text-xs text-warning">
                                  (thiếu giá hoặc số lượng hợp lệ — chưa thể thu)
                                </span>
                              )}
                            </span>
                          </div>

                          {/* Trạng thái + nút */}
                          {isPaid ? (
                            <div className="space-y-2">
                              <div className="flex items-center justify-between gap-2">
                                <span className="inline-flex items-center gap-1.5 rounded-full bg-success-bg px-2.5 py-1 text-xs font-semibold text-success">
                                  <CheckCircle2 size={14} /> Đã thanh toán
                                </span>
                                <button
                                  onClick={() => {
                                    setVoidOpen(voidOpen === k ? null : k);
                                    setVoidReason("");
                                    setErr(null);
                                  }}
                                  disabled={busy === k}
                                  className="inline-flex items-center gap-1 text-xs text-ink-muted hover:text-danger disabled:opacity-50"
                                >
                                  <RotateCcw size={13} /> Hoàn tác
                                </button>
                              </div>
                              {voidOpen === k && (
                                <div className="rounded-lg border border-[#fecaca] bg-[#fff7f7] p-3">
                                  <label
                                    className="block text-xs font-medium text-[#991b1b]"
                                    htmlFor={`void-reason-${r.visit_id}`}
                                  >
                                    Lý do hoàn tác
                                  </label>
                                  <textarea
                                    id={`void-reason-${r.visit_id}`}
                                    value={voidReason}
                                    onChange={(event) =>
                                      setVoidReason(event.target.value)
                                    }
                                    maxLength={500}
                                    rows={2}
                                    placeholder="Ví dụ: Khách đổi phương thức thanh toán"
                                    className="mt-1 w-full rounded-md border border-[#fecaca] bg-white px-2 py-1.5 text-sm text-ink outline-none focus:border-danger"
                                  />
                                  <div className="mt-2 flex items-center gap-2">
                                    <button
                                      onClick={() => togglePaid(r, voidReason)}
                                      disabled={
                                        busy === k ||
                                        voidReason.trim().length < 5
                                      }
                                      className="rounded-md bg-danger px-2.5 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                                    >
                                      {busy === k
                                        ? "Đang hoàn tác…"
                                        : "Xác nhận hoàn tác"}
                                    </button>
                                    <button
                                      onClick={() => {
                                        setVoidOpen(null);
                                        setVoidReason("");
                                      }}
                                      disabled={busy === k}
                                      className="px-2 py-1.5 text-xs text-ink-muted disabled:opacity-50"
                                    >
                                      Hủy
                                    </button>
                                  </div>
                                </div>
                              )}
                            </div>
                          ) : (
                            <div className="space-y-2">
                              <button
                                onClick={() => setPayOpen(open ? null : k)}
                                disabled={missing || sum <= 0}
                                title={
                                  missing
                                    ? "Cần bổ sung đầy đủ giá và số lượng thuốc trước khi thu"
                                    : undefined
                                }
                                className="inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
                              >
                                <QrCode size={15} />
                                {open ? "Ẩn mã QR" : "Thanh toán"}
                              </button>

                              {open && (
                                <div className="rounded-lg border border-dashed border-brand-100 bg-brand-50 p-3">
                                  <div className="flex items-center gap-3">
                                    {/* Ô QR placeholder — chưa nối cổng thanh toán. */}
                                    <div className="flex h-24 w-24 shrink-0 flex-col items-center justify-center rounded-lg border border-line bg-white text-[#c9a3b8]">
                                      <QrCode size={40} />
                                      <span className="mt-1 text-[8px] leading-none">
                                        QR demo
                                      </span>
                                    </div>
                                    <div className="min-w-0 text-xs text-ink-muted">
                                      <p className="font-medium text-brand-800">
                                        Quét mã để thanh toán
                                      </p>
                                      <p className="mt-1">
                                        Mã QR thật sẽ hiện khi nối cổng thanh toán.
                                        BN quét xong → bấm “Đã thanh toán”.
                                      </p>
                                    </div>
                                  </div>
                                  <button
                                    onClick={() => togglePaid(r)}
                                    disabled={busy === k || missing || sum <= 0}
                                    className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-success-bg bg-white px-3 py-1.5 text-sm font-semibold text-success hover:bg-success-bg disabled:opacity-50"
                                  >
                                    <Check size={15} /> {busy === k ? "Đang lưu…" : "Đã thanh toán"}
                                  </button>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
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
}
