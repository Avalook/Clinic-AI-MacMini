"use client";

// Thu tiền theo lượt khám. Tất cả khoản thu và mutation vẫn dùng đúng API
// payment hiện có; màn này chỉ đổi sang workspace ba vùng của bộ thiết kế V2.

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Check,
  CheckCircle2,
  CircleAlert,
  ClipboardList,
  CreditCard,
  Pill,
  QrCode,
  ReceiptText,
  RotateCcw,
  Search,
  Tag,
} from "lucide-react";

import { calculateCashierTotal } from "@/lib/cashier-total";
import { cashierAmountState } from "@/lib/clinical-workspace-policy";
import {
  EmptyWorkspace,
  Monogram,
  PanelHeading,
  WorkspaceMetric,
  WorkspaceMetricRow,
} from "./WorkspacePrimitives";
import workspaceStyles from "./WorkspacePrimitives.module.css";

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
  { label: string; payLabel: string; singular: string; icon: typeof Pill }
> = {
  thuoc: {
    label: "Thu ngân thuốc",
    payLabel: "Thanh toán thuốc",
    singular: "thuốc",
    icon: Pill,
  },
  dich_vu: {
    label: "Thu ngân dịch vụ",
    payLabel: "Thanh toán dịch vụ",
    singular: "dịch vụ",
    icon: Tag,
  },
};

function fmtVnd(value: number | null): string {
  if (value === null) return "Chưa có giá";
  return `${new Intl.NumberFormat("vi-VN").format(value)} ₫`;
}

function hasModeItems(mode: CashierMode, row: CashierRow): boolean {
  return mode === "thuoc" ? row.drugs.length > 0 : row.services.length > 0;
}

function paymentFacts(mode: CashierMode, row: CashierRow) {
  return calculateCashierTotal(mode, row.services, row.drugs);
}

export default function CashierWorkBoard({
  rows,
  modes,
  paidInit = [],
}: {
  rows: CashierRow[];
  /** CASHIER_THUOC=[thuoc], CASHIER_DV=[dich_vu], CASHIER=[thuoc,dich_vu]. */
  modes: CashierMode[];
  /** Dòng payment đã thu từ backend, giữ qua tải lại. */
  paidInit?: { visit_id: string; kind: CashierMode }[];
}) {
  const router = useRouter();
  const [mode, setMode] = useState<CashierMode>(modes[0] ?? "dich_vu");
  const [selectedVisitId, setSelectedVisitId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [payOpen, setPayOpen] = useState<string | null>(null);
  const [paid, setPaid] = useState<Set<string>>(
    () => new Set(paidInit.map((payment) => `${payment.kind}:${payment.visit_id}`)),
  );
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [voidOpen, setVoidOpen] = useState<string | null>(null);
  const [voidReason, setVoidReason] = useState("");

  const meta = MODE_META[mode];
  const Icon = meta.icon;
  const key = (visitId: string) => `${mode}:${visitId}`;
  const normalizedQuery = query.trim().toLocaleLowerCase("vi-VN");
  const shown = useMemo(
    () =>
      rows.filter((row) =>
        !normalizedQuery
          ? true
          : [row.full_name, row.patient_code, row.phone]
              .filter(Boolean)
              .some((value) => value?.toLocaleLowerCase("vi-VN").includes(normalizedQuery)),
      ),
    [normalizedQuery, rows],
  );
  const selected = shown.find((row) => row.visit_id === selectedVisitId) ?? shown[0] ?? null;

  const countWithItems = rows.filter((row) => hasModeItems(mode, row)).length;
  const countPaid = rows.filter((row) => paid.has(key(row.visit_id))).length;
  const countMissing = rows.filter((row) => {
    if (!hasModeItems(mode, row)) return false;
    return paymentFacts(mode, row).missing;
  }).length;
  const amountReady = rows.reduce((total, row) => {
    const facts = paymentFacts(mode, row);
    return facts.missing ? total : total + facts.sum;
  }, 0);

  // Lưu thật qua backend rồi cập nhật state + refresh cho các màn khác.
  async function togglePaid(row: CashierRow, reversalReason?: string) {
    const paymentKey = key(row.visit_id);
    const isPaid = paid.has(paymentKey);
    const normalizedReason = reversalReason?.trim();
    const { sum, missing } = paymentFacts(mode, row);
    if (
      isPaid &&
      (!normalizedReason || normalizedReason.length < 5 || normalizedReason.length > 500)
    ) {
      setErr("Lý do hoàn tác phải có từ 5 đến 500 ký tự.");
      return;
    }
    if (!isPaid && (missing || sum <= 0)) {
      setErr("Chưa thể thu tiền khi còn khoản chưa có giá hoặc số lượng thuốc chưa hợp lệ.");
      return;
    }

    setBusy(paymentKey);
    setErr(null);
    try {
      const response = await fetch("/api/payment", {
        method: isPaid ? "DELETE" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          isPaid
            ? { visitId: row.visit_id, kind: mode, reason: normalizedReason }
            : {
                visitId: row.visit_id,
                clinicPatientId: row.clinic_patient_id,
                kind: mode,
                amount: sum,
              },
        ),
      });
      if (!response.ok) {
        setErr((await response.json().catch(() => ({})))?.error ?? "Lỗi thanh toán.");
        return;
      }
      setPaid((current) => {
        const next = new Set(current);
        if (isPaid) next.delete(paymentKey);
        else next.add(paymentKey);
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

  const selectedFacts = selected ? paymentFacts(mode, selected) : null;
  const selectedKey = selected ? key(selected.visit_id) : null;
  const selectedPaid = selectedKey ? paid.has(selectedKey) : false;
  const selectedPayOpen = selectedKey === payOpen;
  const selectedHasItems = selected ? hasModeItems(mode, selected) : false;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">{meta.label}</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Đối chiếu khoản thu theo lượt khám. Trạng thái thanh toán được lưu qua hệ
          thống hiện có; mã QR chỉ là khung chờ tích hợp cổng thanh toán.
        </p>
      </header>
      <WorkspaceMetricRow>
        <WorkspaceMetric
          label={`Có ${meta.singular} cần thu`}
          value={countWithItems}
          icon={<ClipboardList className="size-5" />}
          tone="brand"
        />
        <WorkspaceMetric
          label="Đã thanh toán"
          value={countPaid}
          icon={<CheckCircle2 className="size-5" />}
          tone="success"
        />
        <WorkspaceMetric
          label="Cần bổ sung giá / SL"
          value={countMissing}
          icon={<CircleAlert className="size-5" />}
          tone={countMissing ? "warning" : "neutral"}
        />
        <WorkspaceMetric
          label="Tạm tính khoản đủ dữ liệu"
          value={fmtVnd(amountReady)}
          icon={<ReceiptText className="size-5" />}
          tone="neutral"
        />
      </WorkspaceMetricRow>

      {err ? (
        <p role="alert" className="rounded-control border border-danger bg-danger-bg px-3 py-2 text-sm text-danger">
          {err}
        </p>
      ) : null}

      {modes.length > 1 ? (
        <div className="inline-flex rounded-card border border-line bg-surface p-1 shadow-card" aria-label="Chọn loại khoản thu">
          {modes.map((candidate) => (
            <button
              type="button"
              key={candidate}
              onClick={() => {
                setMode(candidate);
                setPayOpen(null);
                setVoidOpen(null);
                setVoidReason("");
              }}
              aria-pressed={mode === candidate}
              className={`rounded-control px-3 py-2 text-sm font-medium transition-colors ${
                mode === candidate
                  ? "bg-brand-600 text-white"
                  : "text-ink-soft hover:bg-surface-sunken"
              }`}
            >
              {MODE_META[candidate].label}
            </button>
          ))}
        </div>
      ) : null}

      <div className={workspaceStyles.workspace}>
      <div className={`${workspaceStyles.threeColumn} ${workspaceStyles.cashier}`}>
        <aside
          aria-label="Danh sách khoản thu"
          className="min-w-0 overflow-hidden rounded-card border border-line bg-surface shadow-card"
        >
          <PanelHeading title={meta.label} detail={`${shown.length} lượt khám hiển thị`} />
          <div className="border-b border-line p-3">
            <label className="flex items-center gap-2 rounded-control border border-line bg-surface px-3 py-2 text-ink-muted focus-within:border-brand-500">
              <Search className="size-4 shrink-0" aria-hidden="true" />
              <span className="sr-only">Tìm bệnh nhân, mã BN hoặc số điện thoại</span>
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Tìm bệnh nhân, mã BN"
                className="min-w-0 flex-1 bg-transparent text-xs text-ink outline-none placeholder:text-ink-faint"
              />
            </label>
          </div>
          <div className="max-h-[630px] overflow-y-auto">
            {shown.length ? (
              shown.map((row) => {
                const facts = paymentFacts(mode, row);
                const isPaid = paid.has(key(row.visit_id));
                const hasItems = hasModeItems(mode, row);
                const amountState = cashierAmountState(hasItems, facts.missing);
                return (
                  <button
                    type="button"
                    key={row.visit_id}
                    onClick={() => setSelectedVisitId(row.visit_id)}
                    aria-current={row.visit_id === selected?.visit_id ? "true" : undefined}
                    className={`w-full border-l-[3px] px-3 py-3 text-left transition-colors ${
                      row.visit_id === selected?.visit_id
                        ? "border-brand-500 bg-surface-selected"
                        : "border-transparent bg-surface hover:bg-surface-sunken"
                    }`}
                  >
                    <span className="flex gap-2.5">
                      <Monogram value={row.full_name} />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-semibold text-ink">{row.full_name ?? "Chưa rõ tên"}</span>
                        <span className="mt-0.5 block truncate text-xs text-ink-muted">{row.patient_code ?? "Chưa có mã BN"}</span>
                        <span className="mt-1 flex items-center justify-between gap-2">
                          <span className="text-xs text-ink-faint">
                            {amountState === "empty"
                              ? `Chưa có ${meta.singular}`
                              : amountState === "incomplete"
                                ? "Chưa đủ dữ liệu"
                                : fmtVnd(facts.sum)}
                          </span>
                          <span className={`rounded-chip px-1.5 py-0.5 text-[11px] font-medium ${
                            isPaid ? "bg-success-bg text-success" : !hasItems ? "bg-surface-sunken text-ink-muted" : facts.missing ? "bg-warning-bg text-warning" : "bg-surface-sunken text-ink-muted"
                          }`}>
                            {isPaid ? "Đã thu" : !hasItems ? "Chưa có khoản" : facts.missing ? "Thiếu dữ liệu" : "Chờ thu"}
                          </span>
                        </span>
                      </span>
                    </span>
                  </button>
                );
              })
            ) : (
              <EmptyWorkspace title="Không tìm thấy lượt khám" detail="Thử một tên, mã bệnh nhân hoặc số điện thoại khác." icon={<Search className="size-6" />} />
            )}
          </div>
        </aside>

        <section
          aria-label="Chi tiết khoản thu"
          className="min-w-0 overflow-hidden rounded-card border border-line bg-surface shadow-card"
        >
          <PanelHeading
            title={meta.payLabel}
            detail="Các dòng hiển thị từ chỉ định, dịch vụ và đơn thuốc của lượt khám."
            action={<Icon className="size-5 text-brand-600" aria-hidden="true" />}
          />
          {selected && selectedFacts ? (
            <>
              <div className="border-b border-line px-4 py-3.5">
                <div className="flex items-start gap-3">
                  <Monogram value={selected.full_name} className="size-11 text-sm" />
                  <div className="min-w-0 flex-1">
                    <p className="text-base font-semibold text-ink">{selected.full_name ?? "Chưa rõ tên người bệnh"}</p>
                    <p className="mt-0.5 text-xs text-ink-muted">{selected.patient_code ?? "Chưa có mã BN"}{selected.phone ? ` · ${selected.phone}` : ""}</p>
                  </div>
                </div>
              </div>
              {hasModeItems(mode, selected) ? (
                <div className="overflow-auto">
                  <table className="w-full min-w-[500px] border-collapse text-sm">
                    <thead className="bg-surface-muted text-left text-xs text-ink-muted">
                      <tr>
                        <th className="border-b border-line px-4 py-2.5 font-semibold">Hạng mục</th>
                        <th className="border-b border-line px-4 py-2.5 font-semibold">Quy cách / liều dùng</th>
                        <th className="border-b border-line px-4 py-2.5 text-right font-semibold">Đơn giá</th>
                      </tr>
                    </thead>
                    <tbody>
                      {mode === "dich_vu"
                        ? selected.services.map((item) => (
                            <tr key={item.id} className="hover:bg-surface-muted">
                              <td className="border-b border-line px-4 py-3 font-medium text-ink">{item.name}</td>
                              <td className="border-b border-line px-4 py-3 text-ink-muted">Dịch vụ</td>
                              <td className="border-b border-line px-4 py-3 text-right tabular-nums text-ink-soft">{fmtVnd(item.price)}</td>
                            </tr>
                          ))
                        : selected.drugs.map((item) => (
                            <tr key={item.id} className="hover:bg-surface-muted">
                              <td className="border-b border-line px-4 py-3 font-medium text-ink">{item.name}</td>
                              <td className="border-b border-line px-4 py-3 text-ink-muted">{[item.quantity, item.dosage].filter(Boolean).join(" · ") || "Chưa có liều dùng"}</td>
                              <td className="border-b border-line px-4 py-3 text-right tabular-nums text-ink-soft">{fmtVnd(item.price)}</td>
                            </tr>
                          ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="p-4">
                  <EmptyWorkspace
                    title={`Chưa có ${meta.singular} để thu`}
                    detail="Lượt khám này chưa có dòng dữ liệu phù hợp với quầy thu hiện tại."
                    icon={<ClipboardList className="size-7" />}
                  />
                </div>
              )}
              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line bg-surface-muted px-4 py-3">
                <span className="text-sm text-ink-muted">Tạm tính</span>
                <span className="text-lg font-semibold tabular-nums text-ink">{selectedFacts.missing ? "Chưa đủ dữ liệu" : fmtVnd(selectedFacts.sum)}</span>
              </div>
            </>
          ) : (
            <div className="p-4"><EmptyWorkspace title="Chưa có lượt khám được chọn" detail="Chọn một người bệnh bên trái để xem các khoản thu thực tế." icon={<ReceiptText className="size-7" />} /></div>
          )}
        </section>

        <aside
          aria-label="Trạng thái thanh toán"
          className="min-w-0 overflow-hidden rounded-card border border-line bg-surface shadow-card"
        >
          <PanelHeading title="Trạng thái thanh toán" detail="Thanh toán chỉ được mở khi có đủ giá và số lượng hợp lệ." />
          {selected && selectedFacts && selectedKey ? (
            <div className="space-y-4 p-3.5">
              <section className="rounded-control border border-line bg-surface-muted p-3">
                <div className="flex items-center gap-2">
                  <CreditCard className="size-4 text-brand-600" aria-hidden="true" />
                  <span className="text-xs font-semibold text-ink-soft">Khoản thanh toán</span>
                </div>
                <p className="mt-2 text-lg font-semibold tabular-nums text-ink">{selectedFacts.missing ? "Chưa đủ dữ liệu" : fmtVnd(selectedFacts.sum)}</p>
                {selectedFacts.missing ? (
                  <p className="mt-1 text-xs leading-5 text-warning">Còn khoản chưa có giá hoặc số lượng thuốc chưa hợp lệ; chưa thể thu.</p>
                ) : null}
              </section>

              {!selectedHasItems ? (
                <EmptyWorkspace
                  title={`Chưa có ${meta.singular} để thanh toán`}
                  detail="Hệ thống chưa có dòng khoản thu phù hợp với quầy thu hiện tại."
                  icon={<ClipboardList className="size-7" />}
                />
              ) : selectedPaid ? (
                <section className="space-y-3">
                  <div className="flex items-center gap-2 rounded-control border border-success bg-success-bg px-3 py-2.5 text-sm font-semibold text-success">
                    <CheckCircle2 className="size-4" /> Đã thanh toán
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setVoidOpen(voidOpen === selectedKey ? null : selectedKey);
                      setVoidReason("");
                      setErr(null);
                    }}
                    disabled={busy === selectedKey}
                    className="inline-flex items-center gap-1.5 text-xs font-medium text-ink-muted hover:text-danger disabled:opacity-50"
                  >
                    <RotateCcw className="size-3.5" /> Hoàn tác có lý do
                  </button>
                  {voidOpen === selectedKey ? (
                    <div className="space-y-2 rounded-control border border-danger bg-danger-bg p-3">
                      <label className="block text-xs font-medium text-danger" htmlFor={`void-reason-${selected.visit_id}`}>Lý do hoàn tác</label>
                      <textarea
                        id={`void-reason-${selected.visit_id}`}
                        value={voidReason}
                        onChange={(event) => setVoidReason(event.target.value)}
                        maxLength={500}
                        rows={3}
                        placeholder="Ví dụ: Khách đổi phương thức thanh toán"
                        className="w-full rounded-control border border-danger bg-surface px-2.5 py-2 text-sm text-ink outline-none focus:border-danger"
                      />
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => togglePaid(selected, voidReason)}
                          disabled={busy === selectedKey || voidReason.trim().length < 5}
                          className="rounded-control bg-danger px-3 py-2 text-xs font-semibold text-white disabled:opacity-50"
                        >
                          {busy === selectedKey ? "Đang hoàn tác…" : "Xác nhận hoàn tác"}
                        </button>
                        <button
                          type="button"
                          onClick={() => { setVoidOpen(null); setVoidReason(""); }}
                          disabled={busy === selectedKey}
                          className="rounded-control border border-line bg-surface px-3 py-2 text-xs font-medium text-ink-muted disabled:opacity-50"
                        >
                          Hủy
                        </button>
                      </div>
                    </div>
                  ) : null}
                </section>
              ) : (
                <section className="space-y-3">
                  <button
                    type="button"
                    onClick={() => setPayOpen(selectedPayOpen ? null : selectedKey)}
                    disabled={selectedFacts.missing || selectedFacts.sum <= 0}
                    title={selectedFacts.missing ? "Cần bổ sung đủ giá và số lượng trước khi thu" : undefined}
                    className="inline-flex w-full items-center justify-center gap-2 rounded-control bg-brand-600 px-3 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <QrCode className="size-4" /> {selectedPayOpen ? "Ẩn mã QR" : "Thanh toán"}
                  </button>
                  {selectedPayOpen ? (
                    <div className="space-y-3 rounded-control border border-brand-100 bg-brand-50 p-3">
                      <div className="flex gap-3">
                        <div className="grid size-20 shrink-0 place-items-center rounded-control border border-line bg-surface text-brand-700">
                          <QrCode className="size-9" aria-hidden="true" />
                        </div>
                        <p className="text-xs leading-5 text-ink-muted">
                          Mã QR là khung chờ tích hợp cổng thanh toán. Sau khi xác nhận giao dịch, bấm nút bên dưới để lưu trạng thái thanh toán.
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => togglePaid(selected)}
                        disabled={busy === selectedKey || selectedFacts.missing || selectedFacts.sum <= 0}
                        className="inline-flex w-full items-center justify-center gap-2 rounded-control border border-success bg-surface px-3 py-2.5 text-sm font-semibold text-success hover:bg-success-bg disabled:opacity-50"
                      >
                        <Check className="size-4" /> {busy === selectedKey ? "Đang lưu…" : "Đã thanh toán"}
                      </button>
                    </div>
                  ) : null}
                </section>
              )}
            </div>
          ) : (
            <div className="p-3.5"><EmptyWorkspace title="Chưa có khoản thu được chọn" detail="Chọn một lượt khám từ danh sách để xem trạng thái thanh toán." icon={<CreditCard className="size-7" />} /></div>
          )}
        </aside>
      </div>
      </div>
    </div>
  );
}
