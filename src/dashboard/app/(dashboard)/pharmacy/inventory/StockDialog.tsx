"use client";

// StockDialog — bốn thao tác ghi kho: nhập, xuất, điều chỉnh, huỷ (B.3).
//
// Một hộp thoại cho cả bốn vì chúng khác nhau đúng ở danh sách ô nhập; tách
// thành bốn component thì bốn lần phải nhớ khoá nút lúc đang gửi và bốn lần
// phải nhớ gắn Idempotency-Key.
//
// Về Idempotency-Key: khoá được đúc lúc mở hộp thoại và ĐÚC LẠI mỗi khi người
// dùng sửa một ô. Nhờ vậy bấm đúp / gửi trùng cùng một nội dung dùng lại khoá
// cũ (server trả về kết quả lần trước thay vì nhập thêm một lô nữa), còn sửa số
// rồi gửi lại là một yêu cầu khác thật nên phải có khoá khác — nếu không, lần
// sửa sẽ nhận về đúng cái kết quả sai của lần trước.

import { useState } from "react";

export type StockMode = "receive" | "adjust" | "discard" | "dispense";

export interface DrugOption {
  id: string;
  label: string;
}

export interface BatchTarget {
  id: string;
  batch_code: string;
  quantity_on_hand: number;
  unit: string;
  drugLabel: string;
}

interface Props {
  mode: StockMode;
  drugs: DrugOption[];
  batch: BatchTarget | null;
  onClose: () => void;
  onDone: (message: string) => void;
}

const TITLE: Record<StockMode, string> = {
  receive: "Nhập lô thuốc",
  adjust: "Điều chỉnh tồn",
  discard: "Huỷ hàng",
  dispense: "Xuất kho",
};

const SUBMIT_LABEL: Record<StockMode, string> = {
  receive: "Nhập kho",
  adjust: "Lưu điều chỉnh",
  discard: "Huỷ hàng",
  dispense: "Xuất kho",
};

const fmtQty = (n: number) =>
  new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 3 }).format(n);

const newKey = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;

interface FormState {
  drugCatalogId: string;
  batchCode: string;
  expiryDate: string;
  quantity: string;
  unit: string;
  costPrice: string;
  reason: string;
  wholeBatch: boolean;
}

const EMPTY: FormState = {
  drugCatalogId: "",
  batchCode: "",
  expiryDate: "",
  quantity: "",
  unit: "viên",
  costPrice: "",
  reason: "",
  wholeBatch: true,
};

export default function StockDialog({
  mode,
  drugs,
  batch,
  onClose,
  onDone,
}: Props) {
  const [form, setForm] = useState<FormState>(EMPTY);
  const [idemKey, setIdemKey] = useState(newKey);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sửa ô nào cũng đúc khoá mới: nội dung đã khác thì đây là yêu cầu khác.
  function setField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((f) => ({ ...f, [key]: value }));
    setIdemKey(newKey());
    setError(null);
  }

  const needsBatch = mode === "adjust" || mode === "discard";
  if (needsBatch && !batch) return null;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (pending) return;
    setPending(true);
    setError(null);

    const [path, body] = buildRequest(mode, form, batch);
    try {
      const res = await fetch(path, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": idemKey,
        },
        body: JSON.stringify(body),
      });
      const payload = (await res.json().catch(() => ({}))) as {
        error?: string;
        quantity_on_hand?: string;
      };
      if (!res.ok) {
        setError(payload.error ?? "Không lưu được. Thử lại giúp tôi.");
        setPending(false);
        return;
      }
      onDone(doneMessage(mode, payload.quantity_on_hand));
    } catch {
      setError("Mất kết nối. Kiểm tra mạng rồi thử lại.");
      setPending(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <form
        onSubmit={submit}
        className="w-full max-w-md rounded-control border border-line bg-surface p-4 shadow-lg"
      >
        <h2 className="text-base font-semibold text-ink">{TITLE[mode]}</h2>
        {batch ? (
          <p className="mt-0.5 text-xs text-ink-muted">
            {batch.drugLabel} — lô {batch.batch_code}, còn{" "}
            {fmtQty(batch.quantity_on_hand)} {batch.unit}
          </p>
        ) : null}

        <div className="mt-3 flex flex-col gap-3">
          {(mode === "receive" || mode === "dispense") && (
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-ink-muted">Thuốc</span>
              <select
                required
                value={form.drugCatalogId}
                onChange={(e) => setField("drugCatalogId", e.target.value)}
                className="rounded-control border border-line bg-surface-muted px-2.5 py-1.5 text-ink outline-none focus:border-brand-500"
              >
                <option value="">— Chọn thuốc —</option>
                {drugs.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.label}
                  </option>
                ))}
              </select>
            </label>
          )}

          {mode === "receive" && (
            <>
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-ink-muted">Mã lô</span>
                <input
                  required
                  value={form.batchCode}
                  onChange={(e) => setField("batchCode", e.target.value)}
                  placeholder="LOT-2026-001"
                  className="rounded-control border border-line bg-surface-muted px-2.5 py-1.5 text-ink outline-none focus:border-brand-500"
                />
              </label>
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-ink-muted">Hạn dùng</span>
                <input
                  required
                  type="date"
                  value={form.expiryDate}
                  onChange={(e) => setField("expiryDate", e.target.value)}
                  className="rounded-control border border-line bg-surface-muted px-2.5 py-1.5 text-ink outline-none focus:border-brand-500"
                />
              </label>
            </>
          )}

          {mode === "discard" && (
            <label className="flex items-center gap-2 text-sm text-ink">
              <input
                type="checkbox"
                checked={form.wholeBatch}
                onChange={(e) => setField("wholeBatch", e.target.checked)}
              />
              Huỷ toàn bộ phần còn lại của lô
            </label>
          )}

          {!(mode === "discard" && form.wholeBatch) && (
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-ink-muted">
                {mode === "adjust"
                  ? "Chênh lệch (âm = giảm, dương = tăng)"
                  : "Số lượng"}
              </span>
              <input
                required
                type="number"
                step="0.001"
                {...(mode === "adjust" ? {} : { min: "0.001" })}
                value={form.quantity}
                onChange={(e) => setField("quantity", e.target.value)}
                className="rounded-control border border-line bg-surface-muted px-2.5 py-1.5 text-ink outline-none focus:border-brand-500"
              />
            </label>
          )}

          {mode === "receive" && (
            <div className="grid grid-cols-2 gap-3">
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-ink-muted">Đơn vị</span>
                <input
                  required
                  value={form.unit}
                  onChange={(e) => setField("unit", e.target.value)}
                  className="rounded-control border border-line bg-surface-muted px-2.5 py-1.5 text-ink outline-none focus:border-brand-500"
                />
              </label>
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-ink-muted">Giá nhập (đ)</span>
                <input
                  type="number"
                  min="0"
                  step="1"
                  value={form.costPrice}
                  onChange={(e) => setField("costPrice", e.target.value)}
                  className="rounded-control border border-line bg-surface-muted px-2.5 py-1.5 text-ink outline-none focus:border-brand-500"
                />
              </label>
            </div>
          )}

          <label className="flex flex-col gap-1 text-sm">
            <span className="text-ink-muted">
              Lý do
              {mode === "adjust" || mode === "discard" ? "" : " (không bắt buộc)"}
            </span>
            <input
              required={mode === "adjust" || mode === "discard"}
              minLength={mode === "adjust" || mode === "discard" ? 5 : undefined}
              value={form.reason}
              onChange={(e) => setField("reason", e.target.value)}
              placeholder={
                mode === "discard"
                  ? "Hết hạn 12/2026"
                  : mode === "adjust"
                    ? "Kiểm kê cuối tháng"
                    : ""
              }
              className="rounded-control border border-line bg-surface-muted px-2.5 py-1.5 text-ink outline-none focus:border-brand-500"
            />
          </label>
        </div>

        {error ? (
          <p className="mt-3 rounded-control bg-danger-bg px-3 py-2 text-sm text-danger">
            {error}
          </p>
        ) : null}

        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={pending}
            className="rounded-control border border-line-strong bg-surface px-4 py-2 text-sm font-medium text-ink hover:bg-surface-sunken disabled:cursor-not-allowed disabled:text-ink-faint"
          >
            Thoát
          </button>
          <button
            type="submit"
            disabled={pending}
            className={`rounded-control px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-ink-faint ${
              mode === "discard"
                ? "bg-danger hover:opacity-90"
                : "bg-brand-600 hover:bg-brand-700"
            }`}
          >
            {pending ? "Đang lưu…" : SUBMIT_LABEL[mode]}
          </button>
        </div>
      </form>
    </div>
  );
}

function buildRequest(
  mode: StockMode,
  form: FormState,
  batch: BatchTarget | null,
): [string, Record<string, unknown>] {
  const quantity = form.quantity.trim();
  const reason = form.reason.trim() || null;

  switch (mode) {
    case "receive":
      return [
        "/api/pharmacy/batches",
        {
          drugCatalogId: form.drugCatalogId,
          batchCode: form.batchCode.trim(),
          expiryDate: form.expiryDate,
          quantity,
          unit: form.unit.trim(),
          costPrice: form.costPrice.trim() ? Number(form.costPrice) : null,
          reason,
        },
      ];
    case "adjust":
      return [
        `/api/pharmacy/batches/${batch?.id}/adjust`,
        { quantity, reason },
      ];
    case "discard":
      return [
        `/api/pharmacy/batches/${batch?.id}/discard`,
        { quantity: form.wholeBatch ? null : quantity, reason },
      ];
    case "dispense":
      return [
        "/api/pharmacy/dispense",
        { drugCatalogId: form.drugCatalogId, quantity, reason },
      ];
  }
}

function doneMessage(mode: StockMode, onHand: string | undefined): string {
  const tail = onHand ? ` Tồn còn ${fmtQty(Number(onHand))}.` : "";
  switch (mode) {
    case "receive":
      return `Đã nhập kho.${tail}`;
    case "adjust":
      return `Đã điều chỉnh tồn.${tail}`;
    case "discard":
      return `Đã huỷ hàng.${tail}`;
    case "dispense":
      return "Đã xuất kho theo hạn dùng gần nhất.";
  }
}
