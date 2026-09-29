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
  const [filter, setFilter] = useState<"all" | ExpiryState>("all");
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

  const summary = useMemo(() => {
    let totalUnits = 0;
    let soonCount = 0;
    let expiredCount = 0;
    for (const b of batches) {
      totalUnits += Number(b.quantity_on_hand);
      // Chỉ đếm lô còn thuốc trên kệ (`canh_bao_han` máy chủ trả).
      if (b.canh_bao_han && b.trang_thai_han === "sap_het_han") soonCount++;
      if (b.canh_bao_han && b.trang_thai_han === "het_han") expiredCount++;
    }
    return { totalUnits, soonCount, expiredCount };
  }, [batches]);

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

  const the = (so: string | number, nhan: string, tone?: string) => (
    <div className="rounded-control border border-line bg-surface p-3">
      <div className={`text-title font-semibold ${tone ?? "text-ink"}`}>{so}</div>
      <div className="text-meta text-ink-muted">{nhan}</div>
    </div>
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {the(batches.length, "Lô thuốc")}
        {the(fmtQty(summary.totalUnits), "Tổng tồn (đơn vị)")}
        {the(summary.soonCount, "Lô sắp hết hạn", summary.soonCount > 0 ? "text-warning" : undefined)}
        {the(summary.expiredCount, "Lô hết hạn còn trên kệ", summary.expiredCount > 0 ? "text-danger" : undefined)}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {(["all", "con_han", "sap_het_han", "het_han"] as const).map((f) => (
          <Button
            key={f}
            type="button"
            size="sm"
            variant={filter === f ? "primary" : "secondary"}
            onClick={() => setFilter(f)}
          >
            {f === "all" ? "Tất cả" : STATE_LABEL[f]}
          </Button>
        ))}
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Tìm thuốc / mã lô…"
          aria-label="Tìm lô thuốc"
          className={`${INPUT} sm:ml-auto sm:w-56`}
        />
        {ghiDuoc ? (
          <Button type="button" variant="primary" size="sm" onClick={() => setMoNhap(true)}>
            + Nhập lô
          </Button>
        ) : null}
      </div>

      {moNhap ? <NhapLo thuoc={thuoc} onXong={() => setMoNhap(false)} /> : null}

      <div className={`${TBL_WRAP} overflow-x-auto`}>
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
                  Chưa có lô thuốc nào — bấm [+ Nhập lô] để nhập.
                </td>
              </tr>
            ) : (
              rows.flatMap((b) => {
                const st = b.trang_thai_han;
                const dangMo = lo?.id === b.id;
                const hang = (
                  <tr key={b.id}>
                    <td className="px-3 py-2 font-medium text-ink">
                      {onXemThe && b.drug_catalog_id ? (
                        <button
                          type="button"
                          onClick={() => b.drug_catalog_id && onXemThe(b.drug_catalog_id)}
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
                          <span className="mb-1 block text-meta text-ink-soft">Lý do *</span>
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
