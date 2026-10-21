"use client";

// InventoryBoard — Tồn kho theo lô (image_9 phần kho).
// Bảng lô: mã lô, hạn dùng, tồn, đơn vị, giá nhập, trạng thái (còn hạn / sắp hết
// hạn / hết hạn).
//
// 25/09/2026 (Tuyền: "lô thuốc, ngày nhập xuất, kho để họ tự fill — open cho họ
// thêm"): nhà thuốc tự [+ Nhập lô], và từng lô [Điều chỉnh] (kiểm kê lệch, số có
// dấu) / [Huỷ] (hỏng, hết hạn) — đều bắt lý do. Ba lệnh có sẵn ở máy chủ
// (`receive` · `adjust` · `discard`); tồn chỉ đổi qua sổ kho.

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { CircleCheck, Clock3, Package, Plus, Search, TriangleAlert } from "lucide-react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import { INPUT, TBL_DIV, TBL_HEAD, TBL_WRAP } from "../../form-ui";
import type { ThuocKho } from "./DanhMucKho";
import { guiKho, tienVnd } from "./gui-kho";
import NhapLo from "./NhapLo";

interface InvDrug {
  name_base: string | null;
  name_raw: string | null;
  variant: string | null;
}

export interface InvBatch {
  id: string;
  drug_catalog_id: string | null;
  batch_code: string;
  expiry_date: string;
  quantity_on_hand: number;
  unit: string;
  cost_price: number | null;
  received_at: string | null;
  /** Máy chủ tính theo ngày VN (29/09/2026) — TSX không tự đếm ngày. */
  trang_thai_han: ExpiryState;
  /** Còn thuốc trên kệ VÀ sắp hết hạn / hết hạn (máy chủ tính). */
  canh_bao_han: boolean;
  drug: InvDrug | null;
}

const fmtDate = (iso: string | null) =>
  iso ? new Date(iso).toLocaleDateString("vi-VN") : "—";

const fmtQty = (n: number) =>
  new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 3 }).format(n);

export type ExpiryState = "con_han" | "sap_het_han" | "het_han";

const STATE_LABEL: Record<ExpiryState, string> = {
  con_han: "Còn hạn",
  sap_het_han: "Sắp hết hạn",
  het_han: "Hết hạn",
};

const STATE_TONE: Record<ExpiryState, "success" | "warning" | "danger"> = {
  con_han: "success",
  sap_het_han: "warning",
  het_han: "danger",
};

type ThaoTacLo = { id: string; loai: "adjust" | "discard"; so_luong: string; ly_do: string };

const FILTER_CARDS = [
  { value: "all", label: "Tất cả lô", icon: Package },
  { value: "con_han", label: "Còn hạn", icon: CircleCheck },
  { value: "sap_het_han", label: "Sắp hết hạn", icon: Clock3 },
  { value: "het_han", label: "Hết hạn", icon: TriangleAlert },
] as const;

type InventoryFilter = (typeof FILTER_CARDS)[number]["value"];

const FILTER_CARD_TONE: Record<InventoryFilter, { icon: string; count: string }> = {
  all: { icon: "bg-brand-50 text-brand-700", count: "text-ink" },
  con_han: { icon: "bg-success-bg text-success", count: "text-success" },
  sap_het_han: { icon: "bg-warning-bg text-warning", count: "text-warning" },
  het_han: { icon: "bg-danger-bg text-danger", count: "text-danger" },
};

export default function InventoryBoard({
  batches,
  thuoc,
  ghiDuoc = false,
  onXemThe,
}: {
  batches: InvBatch[];
  thuoc: ThuocKho[];
  /** Có quyền ghi kho — chỉ ẩn/hiện nút, máy chủ tự kiểm. */
  ghiDuoc?: boolean;
  /** Bấm tên thuốc → tab Thẻ kho. */
  onXemThe?: (id: string) => void;
}) {
  const router = useRouter();
  const [filter, setFilter] = useState<InventoryFilter>("all");
  const [search, setSearch] = useState("");
  const [moNhap, setMoNhap] = useState(false);
  const [lo, setLo] = useState<ThaoTacLo | null>(null);
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  const rows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return batches.filter((b) => {
      if (filter !== "all" && b.trang_thai_han !== filter) return false;
      if (!q) return true;
      return (
        b.drug?.name_base?.toLowerCase().includes(q) ||
        b.drug?.name_raw?.toLowerCase().includes(q) ||
        b.batch_code.toLowerCase().includes(q)
      );
    });
  }, [batches, filter, search]);

  const statusCounts = useMemo(
    () => ({
      all: batches.length,
      con_han: batches.filter((b) => b.trang_thai_han === "con_han").length,
      sap_het_han: batches.filter((b) => b.trang_thai_han === "sap_het_han").length,
      het_han: batches.filter((b) => b.trang_thai_han === "het_han").length,
    }),
    [batches],
  );
  const totalUnits = useMemo(
    () => batches.reduce((total, batch) => total + Number(batch.quantity_on_hand), 0),
    [batches],
  );
  const coBoLoc = search.trim() !== "" || filter !== "all";
  const xoaBoLoc = () => {
    setSearch("");
    setFilter("all");
  };

  const guiLo = async () => {
    if (!lo) return;
    setDang(true);
    setLoi(null);
    const kq = await guiKho(lo.loai, {
      drug_batch_id: lo.id,
      so_luong: lo.so_luong.trim(),
      ly_do: lo.ly_do.trim(),
    });
    setDang(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    setLo(null);
    router.refresh();
  };

  return (
    <div className="flex flex-col gap-4">
      <div
        role="group"
        aria-label="Lọc lô thuốc theo hạn dùng"
        className="grid grid-cols-2 gap-3 md:grid-cols-4"
      >
        {FILTER_CARDS.map((card) => {
          const Icon = card.icon;
          const dangChon = filter === card.value;
          const tone = FILTER_CARD_TONE[card.value];
          return (
            <button
              key={card.value}
              type="button"
              aria-label={`${card.label}: ${statusCounts[card.value]} lô`}
              aria-pressed={dangChon}
              onClick={() => setFilter(card.value)}
              className={`flex min-h-20 w-full items-center gap-3 rounded-card border px-3 py-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/30 ${
                dangChon
                  ? "border-brand-600 bg-surface-selected"
                  : "border-line bg-surface hover:bg-surface-muted"
              }`}
            >
              <span
                aria-hidden="true"
                className={`flex size-10 shrink-0 items-center justify-center rounded-control ${tone.icon}`}
              >
                <Icon className="size-5" />
              </span>
              <span className="min-w-0">
                <span className="block truncate text-meta text-ink-muted">{card.label}</span>
                <span className={`block text-title font-semibold tabular-nums ${tone.count}`}>
                  {statusCounts[card.value]}
                </span>
              </span>
            </button>
          );
        })}
      </div>

      <p className="text-right text-meta text-ink-muted">
        Tổng tồn: <span className="font-semibold tabular-nums text-ink">{fmtQty(totalUnits)}</span> đơn vị
      </p>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <div className="relative min-w-0 flex-1">
          <Search
            aria-hidden="true"
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-faint"
          />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Tìm theo tên thuốc, số lô…"
            aria-label="Tìm thuốc hoặc mã lô"
            className={`${INPUT} pl-10`}
          />
        </div>
        {ghiDuoc ? (
          <Button
            type="button"
            variant="primary"
            size="lg"
            onClick={() => setMoNhap(true)}
            className="shrink-0"
          >
            <span className="inline-flex items-center gap-2">
              <Plus aria-hidden="true" className="size-4" />
              Nhập lô
            </span>
          </Button>
        ) : null}
      </div>

      {moNhap ? <NhapLo thuoc={thuoc} onXong={() => setMoNhap(false)} /> : null}

      <ul aria-label="Danh sách lô thuốc" className="space-y-2 md:hidden">
        {rows.length === 0 ? (
          <li className="rounded-card border border-line bg-surface px-3 py-6 text-center">
            <p className="text-body text-ink-muted">
              {coBoLoc ? "Không có lô thuốc phù hợp với bộ lọc." : "Chưa có lô thuốc nào — bấm [Nhập lô] để nhập."}
            </p>
            {coBoLoc ? (
              <Button type="button" size="sm" variant="ghost" aria-label="Xoá bộ lọc" onClick={xoaBoLoc}>
                Xoá bộ lọc
              </Button>
            ) : null}
          </li>
        ) : (
          rows.map((b) => {
            const st = b.trang_thai_han;
            const dangMo = lo?.id === b.id;
            const catalogId = b.drug_catalog_id;
            const tenThuoc = `${b.drug?.name_base ?? b.drug?.name_raw ?? "—"}${b.drug?.variant ? ` (${b.drug.variant})` : ""}`;
            return (
              <li key={b.id} className="rounded-card border border-line bg-surface p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    {onXemThe && catalogId ? (
                      <button
                        type="button"
                        onClick={() => onXemThe(catalogId)}
                        title="Xem thẻ kho"
                        className="text-left text-emph font-semibold text-brand-700 hover:underline"
                      >
                        {tenThuoc}
                      </button>
                    ) : (
                      <p className="text-emph font-semibold text-ink">{tenThuoc}</p>
                    )}
                  </div>
                  <Chip tone={STATE_TONE[st]}>{STATE_LABEL[st]}</Chip>
                </div>

                <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 border-t border-hairline pt-3 text-meta">
                  <div>
                    <dt className="text-ink-faint">Mã lô</dt>
                    <dd className="text-ink">{b.batch_code}</dd>
                  </div>
                  <div>
                    <dt className="text-ink-faint">Hạn dùng</dt>
                    <dd className="text-ink">{fmtDate(b.expiry_date)}</dd>
                  </div>
                  <div>
                    <dt className="text-ink-faint">Tồn</dt>
                    <dd className="font-semibold tabular-nums text-ink">
                      {fmtQty(b.quantity_on_hand)} {b.unit}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-ink-faint">Giá nhập</dt>
                    <dd className="tabular-nums text-ink">{tienVnd(b.cost_price)}</dd>
                  </div>
                </dl>

                {ghiDuoc ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      type="button"
                      size="lg"
                      variant="ghost"
                      aria-label={`Điều chỉnh lô ${b.batch_code}`}
                      onClick={() => {
                        setLoi(null);
                        setLo({ id: b.id, loai: "adjust", so_luong: "", ly_do: "" });
                      }}
                    >
                      Điều chỉnh
                    </Button>
                    <Button
                      type="button"
                      size="lg"
                      variant="ghost"
                      aria-label={`Huỷ lô ${b.batch_code}`}
                      onClick={() => {
                        setLoi(null);
                        setLo({ id: b.id, loai: "discard", so_luong: "", ly_do: "" });
                      }}
                    >
                      Huỷ
                    </Button>
                  </div>
                ) : null}

                {dangMo && lo ? (
                  <div className="mt-3 space-y-2 rounded-control bg-surface-muted p-3">
                    <label className="block">
                      <span className="mb-1 block text-meta text-ink-soft">
                        {lo.loai === "adjust"
                          ? "Lệch kiểm kê (âm = bớt, dương = thêm)"
                          : "Số lượng huỷ"}
                      </span>
                      <input
                        value={lo.so_luong}
                        inputMode="decimal"
                        onChange={(e) => setLo({ ...lo, so_luong: e.target.value })}
                        className={INPUT}
                      />
                    </label>
                    <label className="block">
                      <span className="mb-1 block text-meta text-ink-soft">Lý do</span>
                      <input
                        value={lo.ly_do}
                        onChange={(e) => setLo({ ...lo, ly_do: e.target.value })}
                        placeholder={lo.loai === "adjust" ? "Kiểm kê cuối ngày…" : "Hết hạn, vỡ…"}
                        className={INPUT}
                      />
                    </label>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        type="button"
                        size="lg"
                        variant={lo.loai === "discard" ? "danger" : "primary"}
                        disabled={dang || !lo.so_luong.trim() || !lo.ly_do.trim()}
                        onClick={() => void guiLo()}
                      >
                        {dang ? "Đang lưu…" : lo.loai === "adjust" ? "Lưu điều chỉnh" : "Huỷ thuốc"}
                      </Button>
                      <Button type="button" size="lg" variant="ghost" onClick={() => setLo(null)}>
                        Thôi
                      </Button>
                    </div>
                    {loi ? (
                      <p role="alert" className="text-meta text-danger">
                        {loi}
                      </p>
                    ) : null}
                  </div>
                ) : null}
              </li>
            );
          })
        )}
      </ul>

      <div className={`${TBL_WRAP} hidden overflow-x-auto md:block`}>
        <table className="w-full min-w-2xl text-left text-body">
          <thead className={TBL_HEAD}>
            <tr>
              <th className="px-3 py-2">Thuốc</th>
              <th className="px-3 py-2">Mã lô</th>
              <th className="px-3 py-2">Hạn dùng</th>
              <th className="px-3 py-2 text-right">Tồn</th>
              <th className="px-3 py-2">Đơn vị</th>
              <th className="px-3 py-2 text-right">Giá nhập</th>
              <th className="px-3 py-2">Trạng thái</th>
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody className={TBL_DIV}>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-3 py-6 text-center text-ink-muted">
                  <div className="space-y-2">
                    <p>
                      {coBoLoc ? "Không có lô thuốc phù hợp với bộ lọc." : "Chưa có lô thuốc nào — bấm [Nhập lô] để nhập."}
                    </p>
                    {coBoLoc ? (
                      <Button type="button" size="sm" variant="ghost" aria-label="Xoá bộ lọc" onClick={xoaBoLoc}>
                        Xoá bộ lọc
                      </Button>
                    ) : null}
                  </div>
                </td>
              </tr>
            ) : (
              rows.flatMap((b) => {
                const st = b.trang_thai_han;
                const dangMo = lo?.id === b.id;
                const catalogId = b.drug_catalog_id;
                const hang = (
                  <tr key={b.id}>
                    <td className="px-3 py-2 font-medium text-ink">
                      {onXemThe && catalogId ? (
                        <button
                          type="button"
                          onClick={() => onXemThe(catalogId)}
                          title="Xem thẻ kho"
                          className="text-left font-medium text-brand-700 hover:underline"
                        >
                          {b.drug?.name_base ?? b.drug?.name_raw ?? "—"}
                          {b.drug?.variant ? ` (${b.drug.variant})` : ""}
                        </button>
                      ) : (
                        <>
                          {b.drug?.name_base ?? b.drug?.name_raw ?? "—"}
                          {b.drug?.variant ? ` (${b.drug.variant})` : ""}
                        </>
                      )}
                    </td>
                    <td className="px-3 py-2 text-ink-muted">{b.batch_code}</td>
                    <td className="px-3 py-2 text-ink-muted">{fmtDate(b.expiry_date)}</td>
                    <td className="px-3 py-2 text-right font-semibold tabular-nums text-ink">
                      {fmtQty(b.quantity_on_hand)}
                    </td>
                    <td className="px-3 py-2 text-ink-muted">{b.unit}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-ink-muted">
                      {tienVnd(b.cost_price)}
                    </td>
                    <td className="px-3 py-2">
                      <Chip tone={STATE_TONE[st]}>{STATE_LABEL[st]}</Chip>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 text-right">
                      {ghiDuoc ? (
                        <>
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            onClick={() => {
                              setLoi(null);
                              setLo({ id: b.id, loai: "adjust", so_luong: "", ly_do: "" });
                            }}
                          >
                            Điều chỉnh
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            onClick={() => {
                              setLoi(null);
                              setLo({ id: b.id, loai: "discard", so_luong: "", ly_do: "" });
                            }}
                          >
                            Huỷ
                          </Button>
                        </>
                      ) : null}
                    </td>
                  </tr>
                );
                if (!dangMo || !lo) return [hang];
                return [
                  hang,
                  <tr key={`${b.id}-thao-tac`} className="bg-surface-muted">
                    <td colSpan={8} className="px-3 py-3">
                      <div className="flex flex-wrap items-end gap-2">
                        <label className="block">
                          <span className="mb-1 block text-meta text-ink-soft">
                            {lo.loai === "adjust"
                              ? "Lệch kiểm kê (âm = bớt, dương = thêm)"
                              : "Số lượng huỷ"}
                          </span>
                          <input
                            value={lo.so_luong}
                            inputMode="decimal"
                            onChange={(e) => setLo({ ...lo, so_luong: e.target.value })}
                            className={`${INPUT} sm:w-40`}
                          />
                        </label>
                        <label className="block min-w-0 flex-1">
                          <span className="mb-1 block text-meta text-ink-soft">Lý do</span>
                          <input
                            value={lo.ly_do}
                            onChange={(e) => setLo({ ...lo, ly_do: e.target.value })}
                            placeholder={lo.loai === "adjust" ? "Kiểm kê cuối ngày…" : "Hết hạn, vỡ…"}
                            className={INPUT}
                          />
                        </label>
                        <Button
                          type="button"
                          variant={lo.loai === "discard" ? "danger" : "primary"}
                          disabled={dang || !lo.so_luong.trim() || !lo.ly_do.trim()}
                          onClick={() => void guiLo()}
                        >
                          {dang ? "Đang lưu…" : lo.loai === "adjust" ? "Lưu điều chỉnh" : "Huỷ thuốc"}
                        </Button>
                        <Button type="button" variant="ghost" onClick={() => setLo(null)}>
                          Thôi
                        </Button>
                      </div>
                      {loi ? (
                        <p role="alert" className="mt-2 text-meta text-danger">
                          {loi}
                        </p>
                      ) : null}
                    </td>
                  </tr>,
                ];
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
