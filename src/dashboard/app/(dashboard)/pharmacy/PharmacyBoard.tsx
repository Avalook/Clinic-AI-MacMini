"use client";

// PharmacyBoard — màn hình chính Nhà thuốc (image_8 + image_9).
// 2 cột: danh sách đơn thuốc (trái) + chi tiết đơn + tồn kho (phải).
// Dược sĩ xem đơn, kiểm tra tồn kho theo lô/hạn dùng.

import { useMemo, useState } from "react";
import { VN_TZ } from "../../../lib/datetime";
import ThaoTacCapPhat, { type LoThuoc } from "./ThaoTacCapPhat";

interface RxPatient {
  full_name: string | null;
  phone_primary: string | null;
}

interface RxRow {
  id: string;
  source_ref: string | null;
  drug_name_raw: string | null;
  dosage_instructions: string | null;
  quantity: string | null;
  quantity_note: string | null;
  quantity_num: number | null;
  unit: string | null;
  dispensed_qty: number | null;
  dispense_status: string | null;
  closed_at: string | null;
  created_at: string | null;
  patient: RxPatient | null;
  visit: { visit_id: string } | null;
}

interface BatchDrug {
  name_base: string | null;
  name_raw: string | null;
  variant: string | null;
}

interface BatchRow {
  id: string;
  batch_code: string;
  expiry_date: string;
  quantity_on_hand: number;
  unit: string;
  cost_price: number | null;
  drug: BatchDrug | null;
}

interface Props {
  prescriptions: RxRow[];
  inventory: BatchRow[];
}

const fmtDate = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString("vi-VN", { timeZone: VN_TZ }) : "—";

/** Các lô còn hàng khớp tên thuốc của đơn.
 *
 *  Khớp bằng cách so chuỗi thường-hoá, cùng luật mà phần "tồn kho cho đơn này"
 *  ở dưới đang dùng. Không khớp được thì trả rỗng, và ô chọn hiện câu "kho
 *  chưa có lô nào" — thà nói không tìm thấy còn hơn mời chọn nhầm thuốc. */
function loHopVoiDon(drugName: string | null, inventory: BatchRow[]): LoThuoc[] {
  const ten = (drugName ?? "").trim().toLowerCase();
  if (!ten) return [];
  return inventory
    .filter((b) => {
      if (b.quantity_on_hand <= 0) return false;
      const ungVien = [b.drug?.name_base, b.drug?.name_raw]
        .filter(Boolean)
        .map((x) => String(x).toLowerCase());
      return ungVien.some((x) => ten.includes(x) || x.includes(ten));
    })
    .map((b) => ({
      id: b.id,
      batch_code: b.batch_code,
      expiry_date: b.expiry_date,
      quantity_on_hand: Number(b.quantity_on_hand),
      unit: b.unit,
      ten: b.drug?.name_base ?? b.drug?.name_raw ?? "",
    }));
}

const fmtQty = (n: number) =>
  new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 3 }).format(n);

export default function PharmacyBoard({ prescriptions, inventory }: Props) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const selected = useMemo(
    () => prescriptions.find((p) => p.id === selectedId) ?? null,
    [prescriptions, selectedId],
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return prescriptions;
    return prescriptions.filter(
      (p) =>
        p.patient?.full_name?.toLowerCase().includes(q) ||
        p.drug_name_raw?.toLowerCase().includes(q) ||
        p.source_ref?.toLowerCase().includes(q),
    );
  }, [prescriptions, search]);

  // Tồn kho theo tên thuốc (gộp lô)
  const stockByDrug = useMemo(() => {
    const map = new Map<string, { total: number; batches: BatchRow[] }>();
    for (const b of inventory) {
      const name = b.drug?.name_base ?? b.drug?.name_raw ?? "Chưa đặt tên";
      const entry = map.get(name) ?? { total: 0, batches: [] };
      entry.total += b.quantity_on_hand;
      entry.batches.push(b);
      map.set(name, entry);
    }
    return map;
  }, [inventory]);

  return (
    <div className="grid h-full grid-cols-[minmax(320px,380px)_1fr] gap-4 p-4">
      {/* ---- Cột trái: danh sách đơn thuốc ---- */}
      <section className="flex flex-col rounded-control border border-line bg-surface">
        <div className="border-b border-line p-3">
          <h2 className="text-sm font-semibold text-ink">Đơn thuốc hôm nay</h2>
          <p className="mt-0.5 text-xs text-ink-muted">
            {prescriptions.length} đơn · {filtered.length} hiển thị
          </p>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Tìm tên BN / thuốc / mã đơn…"
            className="mt-2 w-full rounded-control border border-line bg-surface-muted px-2.5 py-1.5 text-sm text-ink outline-none focus:border-brand-500"
          />
        </div>
        <div className="flex-1 overflow-y-auto">
          {filtered.length === 0 ? (
            <p className="p-4 text-sm text-ink-muted">Chưa có đơn thuốc hôm nay.</p>
          ) : (
            filtered.map((rx) => (
              <button
                key={rx.id}
                onClick={() => setSelectedId(rx.id)}
                className={`block w-full border-b border-line px-3 py-2.5 text-left transition-colors hover:bg-surface-muted ${
                  selectedId === rx.id ? "bg-surface-selected" : ""
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium text-ink">
                    {rx.patient?.full_name ?? "Chưa có tên"}
                  </span>
                  <span className="shrink-0 text-xs text-ink-faint">
                    {fmtDate(rx.created_at)}
                  </span>
                </div>
                <div className="mt-0.5 truncate text-xs text-ink-muted">
                  {rx.drug_name_raw ?? "—"} · SL {rx.quantity ?? "—"}
                </div>
                {rx.patient?.phone_primary && (
                  <div className="mt-0.5 text-xs text-ink-faint">
                    {rx.patient.phone_primary}
                  </div>
                )}
              </button>
            ))
          )}
        </div>
      </section>

      {/* ---- Cột phải: chi tiết đơn + tồn kho ---- */}
      <section className="flex flex-col gap-4 overflow-y-auto">
        {selected ? (
          <div className="rounded-control border border-line bg-surface p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-base font-semibold text-ink">
                  {selected.patient?.full_name ?? "Chưa có tên"}
                </h3>
                <p className="mt-0.5 text-xs text-ink-muted">
                  {selected.patient?.phone_primary ?? "—"} ·{" "}
                  {selected.source_ref ?? "Chưa có mã đơn"}
                </p>
              </div>
              <span className="rounded-full bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700">
                {fmtDate(selected.created_at)}
              </span>
            </div>

            <div className="mt-4 rounded-control border border-line bg-surface-muted p-3">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-soft">
                Thuốc kê
              </h4>
              <div className="mt-2 text-sm text-ink">
                {selected.drug_name_raw ?? "—"}
              </div>
              {selected.dosage_instructions && (
                <div className="mt-1 text-xs text-ink-muted">
                  Liều dùng: {selected.dosage_instructions}
                </div>
              )}
              <div className="mt-1 text-xs text-ink-muted">
                Số lượng: {selected.quantity ?? "—"}
                {selected.quantity_note ? ` (${selected.quantity_note})` : ""}
              </div>
            </div>

            {/* Tồn kho theo thuốc */}
            <div className="mt-4">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-soft">
                Tồn kho theo lô
              </h4>
              {selected.drug_name_raw ? (
                (() => {
                  const name = selected.drug_name_raw.toLowerCase();
                  const matches = [...stockByDrug.entries()].filter(([k]) =>
                    k.toLowerCase().includes(name),
                  );
                  if (matches.length === 0) {
                    return (
                      <p className="mt-2 text-sm text-warning">
                        Không tìm thấy thuốc này trong kho.
                      </p>
                    );
                  }
                  return (
                    <div className="mt-2 space-y-2">
                      {matches.map(([drugName, { total, batches }]) => (
                        <div
                          key={drugName}
                          className="rounded-control border border-line p-3"
                        >
                          <div className="flex items-center justify-between">
                            <span className="text-sm font-medium text-ink">
                              {drugName}
                            </span>
                            <span
                              className={`text-sm font-semibold ${
                                total > 0 ? "text-success" : "text-danger"
                              }`}
                            >
                              {fmtQty(total)} {batches[0]?.unit ?? ""}
                            </span>
                          </div>
                          <div className="mt-2 space-y-1">
                            {batches.map((b) => (
                              <div
                                key={b.id}
                                className="flex items-center justify-between text-xs text-ink-muted"
                              >
                                <span>
                                  Lô {b.batch_code} · HSD{" "}
                                  {new Date(b.expiry_date).toLocaleDateString(
                                    "vi-VN",
                                  )}
                                </span>
                                <span>{fmtQty(b.quantity_on_hand)}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  );
                })()
              ) : (
                <p className="mt-2 text-sm text-ink-muted">
                  Đơn chưa có tên thuốc.
                </p>
              )}
            </div>

            {/* Ba nút của dược sĩ. Lô truyền vào đã lọc theo tên thuốc của
                đơn — đưa cả kho vào ô chọn thì lần cấp nhầm thuốc chỉ còn cách
                một cú bấm. */}
            <div className="mt-4">
              <ThaoTacCapPhat
                prescriptionId={selected.id}
                drugName={selected.drug_name_raw}
                quantityNum={selected.quantity_num}
                quantityText={selected.quantity}
                dispensedQty={Number(selected.dispensed_qty ?? 0)}
                dispenseStatus={selected.dispense_status}
                closed={selected.closed_at !== null}
                batches={loHopVoiDon(selected.drug_name_raw, inventory)}
              />
            </div>
          </div>
        ) : (
          <div className="flex flex-1 items-center justify-center rounded-control border border-dashed border-line text-sm text-ink-faint">
            Chọn một đơn thuốc để xem chi tiết
          </div>
        )}

        {/* Tồn kho tổng quan */}
        <div className="rounded-control border border-line bg-surface p-4">
          <h3 className="text-sm font-semibold text-ink">Tồn kho hiện tại</h3>
          <p className="mt-0.5 text-xs text-ink-muted">
            {inventory.length} lô thuốc còn hàng
          </p>
          <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
            {[...stockByDrug.entries()].map(([name, { total, batches }]) => (
              <div
                key={name}
                className="rounded-control border border-line bg-surface-muted p-2.5"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-ink">{name}</span>
                  <span className="text-xs font-semibold text-ink-soft">
                    {fmtQty(total)} {batches[0]?.unit ?? ""}
                  </span>
                </div>
                <div className="mt-1 text-[11px] text-ink-faint">
                  {batches.length} lô · HSD gần nhất{" "}
                  {new Date(
                    Math.min(...batches.map((b) => +new Date(b.expiry_date))),
                  ).toLocaleDateString("vi-VN")}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}