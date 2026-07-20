"use client";

// 2 view "Thu ngân thuốc" / "Thu ngân dịch vụ" + bảng giá khung CRUD scaffold.
// Ghi qua /api/service-price (service-role) rồi router.refresh() nạp lại từ server.
// DỰNG KHUNG: đơn giá có thể để trống (nhập sau); chưa có luồng thu tiền thực tế.

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Trash2 } from "lucide-react";
import { INPUT, LABEL, BTN } from "../form-ui";

export type PriceGroup = "thuoc" | "dich_vu";

export interface PriceRow {
  id: string;
  service_code: string;
  name: string;
  group: PriceGroup;
  unit_price: number | null;
  active: boolean;
}

const VIEW_LABEL: Record<PriceGroup, string> = {
  thuoc: "Thu ngân thuốc",
  dich_vu: "Thu ngân dịch vụ",
};
const VIEWS: PriceGroup[] = ["thuoc", "dich_vu"];

function fmtVnd(v: number | null): string {
  if (v === null) return "— chưa nhập";
  return new Intl.NumberFormat("vi-VN").format(v) + " ₫";
}

export default function CashierView({
  rows,
  group: lockedGroup,
}: {
  rows: PriceRow[];
  /** Khoá vào 1 nhóm (trang Bảng giá thuốc / dịch vụ riêng) → ẩn toggle. */
  group?: PriceGroup;
}) {
  const router = useRouter();
  const [view, setView] = useState<PriceGroup>(lockedGroup ?? "thuoc");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form thêm dòng giá mới.
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [price, setPrice] = useState("");
  // Bản nháp đơn giá đang sửa theo từng dòng (id → chuỗi nhập).
  const [draft, setDraft] = useState<Record<string, string>>({});

  const visible = useMemo(
    () => rows.filter((r) => r.group === view),
    [rows, view],
  );

  async function send(method: string, body: unknown): Promise<boolean> {
    setError(null);
    setBusy(true);
    const res = await fetch("/api/service-price", {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    setBusy(false);
    if (!res.ok) {
      setError((await res.json().catch(() => ({}))).error ?? "Có lỗi xảy ra.");
      return false;
    }
    router.refresh();
    return true;
  }

  async function add() {
    const ok = await send("POST", {
      service_code: code.trim(),
      name: name.trim(),
      group: view,
      unit_price: price.trim() === "" ? null : price.trim(),
    });
    if (ok) {
      setCode("");
      setName("");
      setPrice("");
    }
  }

  async function savePrice(id: string) {
    const raw = draft[id];
    if (raw === undefined) return;
    const ok = await send("PATCH", {
      id,
      unit_price: raw.trim() === "" ? null : raw.trim(),
    });
    if (ok) setDraft((d) => ({ ...d, [id]: undefined as unknown as string }));
  }

  async function toggleActive(r: PriceRow) {
    await send("PATCH", { id: r.id, active: !r.active });
  }

  async function remove(id: string) {
    await send("DELETE", { id });
  }

  return (
    <div className="space-y-4">
      {/* Toggle 2 view — chỉ hiện khi KHÔNG khoá nhóm (trang gộp cũ). Trang
          Bảng giá thuốc / dịch vụ truyền group → ẩn toggle. */}
      {!lockedGroup && (
        <div className="inline-flex rounded-xl border border-[#e4e4e7] bg-white p-1 shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
          {VIEWS.map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={
                "rounded-lg px-4 py-1.5 text-sm font-medium transition-colors " +
                (view === v
                  ? "bg-[#ec4899] text-white"
                  : "text-[#52525b] hover:bg-[#fdf2f8]")
              }
            >
              {VIEW_LABEL[v]}
            </button>
          ))}
        </div>
      )}

      {error && (
        <p className="rounded bg-[#fee2e2] px-3 py-2 text-sm text-[#dc2626]">
          {error}
        </p>
      )}

      {/* Form thêm dòng giá */}
      <div className="rounded-xl border border-[#e4e4e7] bg-white p-4 shadow-[0_1px_3px_rgba(0,0,0,0.06)]">
        <h2 className="mb-3 text-sm font-semibold text-[#171717]">
          Thêm vào bảng giá — {VIEW_LABEL[view]}
        </h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div>
            <label className={LABEL}>Mã</label>
            <input
              className={INPUT}
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="VD: KH01"
            />
          </div>
          <div>
            <label className={LABEL}>Tên</label>
            <input
              className={INPUT}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Tên dịch vụ / thuốc"
            />
          </div>
          <div>
            <label className={LABEL}>Đơn giá (₫) — để trống nếu chưa chốt</label>
            <input
              className={INPUT}
              value={price}
              inputMode="numeric"
              onChange={(e) => setPrice(e.target.value)}
              placeholder="(trống)"
            />
          </div>
        </div>
        <div className="mt-3">
          <button onClick={add} disabled={busy} className={BTN}>
            {busy ? "Đang lưu..." : "+ Thêm dòng giá"}
          </button>
        </div>
      </div>

      {/* Bảng giá */}
      <div className="overflow-auto rounded-xl border border-[#ececec] bg-white shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
        <table className="w-full min-w-max border-collapse text-sm">
          <thead className="bg-[#fafafa]">
            <tr>
              <th className="border-b border-[#ececec] px-3 py-2 text-left font-semibold text-[#525252]">
                Mã
              </th>
              <th className="border-b border-[#ececec] px-3 py-2 text-left font-semibold text-[#525252]">
                Tên
              </th>
              <th className="border-b border-[#ececec] px-3 py-2 text-left font-semibold text-[#525252]">
                Đơn giá
              </th>
              <th className="border-b border-[#ececec] px-3 py-2 text-left font-semibold text-[#525252]">
                Hiệu lực
              </th>
              <th className="border-b border-[#ececec] px-3 py-2 text-right font-semibold text-[#525252]">
                {""}
              </th>
            </tr>
          </thead>
          <tbody>
            {visible.length === 0 ? (
              <tr>
                <td className="px-3 py-6 text-center text-[#888888]" colSpan={5}>
                  Chưa có dòng giá nào trong {VIEW_LABEL[view].toLowerCase()}.
                </td>
              </tr>
            ) : (
              visible.map((r) => {
                const d = draft[r.id];
                const editing = d !== undefined;
                return (
                  <tr key={r.id} className="hover:bg-[#fafafa]">
                    <td className="border-b border-[#f3f3f3] px-3 py-2 font-mono text-xs text-[#52525b]">
                      {r.service_code}
                    </td>
                    <td className="border-b border-[#f3f3f3] px-3 py-2 text-[#171717]">
                      {r.name}
                    </td>
                    <td className="border-b border-[#f3f3f3] px-3 py-2">
                      <div className="flex items-center gap-2">
                        <input
                          className="h-8 w-32 rounded-md border border-[#e4e4e7] px-2 text-sm tabular-nums outline-none focus:border-[#ec4899]"
                          inputMode="numeric"
                          value={
                            editing ? d : r.unit_price === null ? "" : String(r.unit_price)
                          }
                          placeholder="(trống)"
                          onChange={(e) =>
                            setDraft((s) => ({ ...s, [r.id]: e.target.value }))
                          }
                        />
                        {editing ? (
                          <button
                            onClick={() => savePrice(r.id)}
                            disabled={busy}
                            className="rounded-md bg-[#ec4899] px-2 py-1 text-xs font-medium text-white disabled:opacity-50"
                          >
                            Lưu
                          </button>
                        ) : (
                          <span className="text-xs text-[#a1a1aa]">
                            {fmtVnd(r.unit_price)}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="border-b border-[#f3f3f3] px-3 py-2">
                      <label className="inline-flex cursor-pointer items-center gap-1.5 text-xs text-[#52525b]">
                        <input
                          type="checkbox"
                          checked={r.active}
                          disabled={busy}
                          onChange={() => toggleActive(r)}
                        />
                        {r.active ? "Đang dùng" : "Tắt"}
                      </label>
                    </td>
                    <td className="border-b border-[#f3f3f3] px-3 py-2 text-right">
                      <button
                        onClick={() => remove(r.id)}
                        disabled={busy}
                        aria-label="Xoá"
                        className="rounded-md p-1.5 text-[#a1a1aa] hover:bg-[#fee2e2] hover:text-[#dc2626] disabled:opacity-50"
                      >
                        <Trash2 size={15} />
                      </button>
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
