"use client";

// "Công việc của tôi" của vai THU NGÂN — màn THU TIỀN theo buổi khám (T-DASH-CASHIER-PAY-01).
// TRÁI: danh sách BN đang khám hôm nay (ô gộp: tên + mã + SĐT). PHẢI: khoản thu
//   • Dịch vụ  → service_log của BN hôm nay (ĐỒNG BỘ thật).
//   • Thuốc    → prescription của lượt khám (ĐỒNG BỘ thật).
// Nút "Thanh toán" → hiện khu mã QR (PLACEHOLDER, chưa nối cổng) → "Đã thanh toán".
// LƯU Ý: chưa có bảng billing → trạng thái "đã thanh toán" CHỈ ở client (chưa lưu).
// Giá lấy best-effort từ service_price (khớp tên); chưa có → để trống.

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { QrCode, Check, CheckCircle2, RotateCcw, Pill, Tag } from "lucide-react";

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
  "border-b border-[#ececec] px-4 py-2.5 text-left font-semibold text-[#525252]";
const TD = "border-b border-[#f3f3f3] px-4 py-3 align-top text-[#171717]";

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

  const meta = MODE_META[mode];
  const key = (visitId: string) => `${mode}:${visitId}`;

  // Lưu THẬT vào bảng payment (service-role) rồi cập nhật state + refresh để màn
  // Lễ tân (thanh tiến trình) đồng bộ qua realtime.
  async function togglePaid(r: CashierRow) {
    const k = key(r.visit_id);
    const isPaid = paid.has(k);
    setBusy(k);
    setErr(null);
    const { sum } = rowTotal(r);
    const res = await fetch("/api/payment", {
      method: isPaid ? "DELETE" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(
        isPaid
          ? { visitId: r.visit_id, kind: mode }
          : {
              visitId: r.visit_id,
              clinicPatientId: r.clinic_patient_id,
              kind: mode,
              amount: sum,
            },
      ),
    });
    setBusy(null);
    if (!res.ok) {
      setErr((await res.json().catch(() => ({})))?.error ?? "Lỗi thanh toán.");
      return;
    }
    setPaid((s) => {
      const next = new Set(s);
      if (isPaid) next.delete(k);
      else next.add(k);
      return next;
    });
    setPayOpen(null);
    router.refresh();
  }

  // Tổng tạm tính (chỉ cộng khoản CÓ giá; còn lại để trống → không bịa tổng).
  const rowTotal = (r: CashierRow): { sum: number; missing: boolean } => {
    const items =
      mode === "thuoc"
        ? r.drugs.map((d) => d.price)
        : r.services.map((s) => s.price);
    let sum = 0;
    let missing = false;
    for (const p of items) {
      if (p === null) missing = true;
      else sum += p;
    }
    return { sum, missing };
  };

  const hasItems = (r: CashierRow) =>
    mode === "thuoc" ? r.drugs.length > 0 : r.services.length > 0;

  const shown = useMemo(() => rows, [rows]);

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold text-[#171717]">Công việc của tôi</h1>
        <p className="text-sm text-[#888888]">
          Thu tiền theo buổi khám hôm nay. Dịch vụ &amp; thuốc lấy thật từ hồ sơ khám.
          Trạng thái “Đã thanh toán” được LƯU &amp; đồng bộ với thanh tiến trình bên
          Lễ tân. Mã QR là placeholder (chưa nối cổng thanh toán thật).
        </p>
      </header>

      {err && (
        <p className="rounded bg-[#fee2e2] px-3 py-2 text-sm text-[#dc2626]">{err}</p>
      )}

      {/* Toggle 2 mode — chỉ khi vai thấy cả hai (CASHIER superset). */}
      {modes.length > 1 && (
        <div className="inline-flex rounded-xl border border-[#e4e4e7] bg-white p-1 shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
          {modes.map((m) => (
            <button
              key={m}
              onClick={() => {
                setMode(m);
                setPayOpen(null);
              }}
              className={
                "rounded-lg px-4 py-1.5 text-sm font-medium transition-colors " +
                (mode === m
                  ? "bg-[#ec4899] text-white"
                  : "text-[#52525b] hover:bg-[#fdf2f8]")
              }
            >
              {MODE_META[m].label}
            </button>
          ))}
        </div>
      )}

      <div className="overflow-auto rounded-xl border border-[#ececec] bg-white shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
        <table className="w-full min-w-max border-collapse text-sm">
          <thead className="bg-[#fafafa]">
            <tr>
              <th className={`${TH} min-w-[220px]`}>Bệnh nhân</th>
              <th className={`${TH} min-w-[360px]`}>{meta.payLabel}</th>
            </tr>
          </thead>
          <tbody>
            {shown.length === 0 ? (
              <tr>
                <td className="px-4 py-6 text-center text-[#888888]" colSpan={2}>
                  Chưa có bệnh nhân đang khám hôm nay.
                </td>
              </tr>
            ) : (
              shown.map((r) => {
                const k = key(r.visit_id);
                const isPaid = paid.has(k);
                const open = payOpen === k;
                const { sum, missing } = rowTotal(r);
                return (
                  <tr key={r.visit_id} className="hover:bg-[#fafafa]">
                    {/* Ô 1 — BN gộp: tên + mã + SĐT. */}
                    <td className={TD}>
                      <div className="font-semibold text-[#171717]">
                        {r.full_name ?? "—"}
                      </div>
                      <div className="mt-0.5 font-mono text-xs text-[#888888]">
                        {r.patient_code ?? "—"}
                      </div>
                      <div className="text-xs text-[#71717a]">
                        {r.phone ?? "—"}
                      </div>
                    </td>

                    {/* Ô 2 — khoản thu (dịch vụ/thuốc) + nút Thanh toán → QR. */}
                    <td className={TD}>
                      {!hasItems(r) ? (
                        <span className="text-sm text-[#a1a1aa]">
                          — chưa có {mode === "thuoc" ? "thuốc" : "dịch vụ"} —
                        </span>
                      ) : (
                        <div className="space-y-2">
                          <ul className="divide-y divide-[#f4f4f5] rounded-lg border border-[#eee]">
                            {mode === "dich_vu"
                              ? r.services.map((s) => (
                                  <li
                                    key={s.id}
                                    className="flex items-center justify-between gap-3 px-3 py-1.5"
                                  >
                                    <span className="min-w-0 truncate text-[#171717]">
                                      {s.name}
                                    </span>
                                    <span className="shrink-0 tabular-nums text-[#52525b]">
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
                                      <span className="text-[#171717]">{d.name}</span>
                                      {(d.quantity || d.dosage) && (
                                        <span className="ml-1 text-xs text-[#888888]">
                                          {[d.quantity, d.dosage]
                                            .filter(Boolean)
                                            .join(" · ")}
                                        </span>
                                      )}
                                    </span>
                                    <span className="shrink-0 tabular-nums text-[#52525b]">
                                      {fmtVnd(d.price)}
                                    </span>
                                  </li>
                                ))}
                          </ul>

                          <div className="flex items-center justify-between gap-2 text-sm">
                            <span className="text-[#71717a]">
                              Tạm tính:{" "}
                              <span className="font-semibold text-[#171717] tabular-nums">
                                {fmtVnd(sum)}
                              </span>
                              {missing && (
                                <span className="ml-1 text-xs text-[#a16207]">
                                  (một số khoản chưa có giá)
                                </span>
                              )}
                            </span>
                          </div>

                          {/* Trạng thái + nút */}
                          {isPaid ? (
                            <div className="flex items-center justify-between gap-2">
                              <span className="inline-flex items-center gap-1.5 rounded-full bg-[#dcfce7] px-2.5 py-1 text-xs font-semibold text-[#15803d]">
                                <CheckCircle2 size={14} /> Đã thanh toán
                              </span>
                              <button
                                onClick={() => togglePaid(r)}
                                disabled={busy === k}
                                className="inline-flex items-center gap-1 text-xs text-[#71717a] hover:text-[#dc2626] disabled:opacity-50"
                              >
                                <RotateCcw size={13} /> Hoàn tác
                              </button>
                            </div>
                          ) : (
                            <div className="space-y-2">
                              <button
                                onClick={() => setPayOpen(open ? null : k)}
                                className="inline-flex items-center gap-1.5 rounded-lg bg-[#ec4899] px-3 py-2 text-sm font-semibold text-white hover:bg-[#db2777]"
                              >
                                <QrCode size={15} />
                                {open ? "Ẩn mã QR" : "Thanh toán"}
                              </button>

                              {open && (
                                <div className="rounded-lg border border-dashed border-[#f3cfe0] bg-[#fdf7fb] p-3">
                                  <div className="flex items-center gap-3">
                                    {/* Ô QR placeholder — chưa nối cổng thanh toán. */}
                                    <div className="flex h-24 w-24 shrink-0 flex-col items-center justify-center rounded-lg border border-[#e4e4e7] bg-white text-[#c9a3b8]">
                                      <QrCode size={40} />
                                      <span className="mt-1 text-[8px] leading-none">
                                        QR demo
                                      </span>
                                    </div>
                                    <div className="min-w-0 text-xs text-[#71717a]">
                                      <p className="font-medium text-[#9d2463]">
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
                                    disabled={busy === k}
                                    className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-[#bbf7d0] bg-white px-3 py-1.5 text-sm font-semibold text-[#15803d] hover:bg-[#f0fdf4] disabled:opacity-50"
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
