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
import { guiKho, tienVnd, tonTheoDonVi, tongTonTheoDonVi } from "./gui-kho";
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
  expiry_date: string | null;
  quantity_on_hand: number;
  unit: string;
  cost_price: number | null;
  received_at: string | null;
  /** Máy chủ tính theo ngày VN (29/09/2026) — TSX không tự đếm ngày. */
  trang_thai_han: ExpiryState;
  /** Còn thuốc trên kệ VÀ sắp hết hạn / hết hạn (máy chủ tính). */
  canh_bao_han: boolean;
  huy_lo_txn_id: string | null;
  /** G7: nơi chứa — chỉ có nghĩa khi cơ sở bật tách kho / quầy. */
  noi_chua?: "KHO" | "QUAY";
  drug: InvDrug | null;
}

const fmtDate = (iso: string | null) =>
  iso ? new Date(iso).toLocaleDateString("vi-VN") : "—";

const fmtQty = (n: number) =>
  new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 3 }).format(n);

export type ExpiryState = "con_han" | "sap_het_han" | "het_han" | "chua_co_han";

const STATE_LABEL: Record<ExpiryState, string> = {
  con_han: "Còn hạn",
  sap_het_han: "Sắp hết hạn",
  het_han: "Hết hạn",
  chua_co_han: "Chưa có hạn",
};

const STATE_TONE: Record<ExpiryState, "success" | "warning" | "danger" | "neutral"> = {
  con_han: "success",
  sap_het_han: "warning",
  het_han: "danger",
  chua_co_han: "neutral",
};

type ThaoTacLo = { id: string; loai: "adjust" | "discard" | "sua-lo" | "huy-lo-het-han"; so_luong: string; ly_do: string; batch_code?: string; expiry_date?: string; khoa?: string };

export interface CauHinhHan { so_ngay_sap_het_han: number; sua_canh_bao_duoc: boolean }

export default function InventoryBoard({
  batches,
  thuoc,
  ghiDuoc = false,
  onXemThe,
  cauHinhHan,
  tachKhoQuay = false,
}: {
  batches: InvBatch[];
  thuoc: ThuocKho[];
  /** Có quyền ghi kho — chỉ ẩn/hiện nút, máy chủ tự kiểm. */
  ghiDuoc?: boolean;
  /** G7: cơ sở bật tách kho / quầy → mỗi dòng lô có chip KHO / QUẦY. */
  tachKhoQuay?: boolean;
  /** Bấm tên thuốc → tab Thẻ kho. */
  onXemThe?: (id: string) => void;
  cauHinhHan?: CauHinhHan;
}) {
  const router = useRouter();
  const [filter, setFilter] = useState<"all" | ExpiryState>("all");
  const [search, setSearch] = useState("");
  const [moNhap, setMoNhap] = useState(false);
  const [lo, setLo] = useState<ThaoTacLo | null>(null);
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [ngay, setNgay] = useState(String(cauHinhHan?.so_ngay_sap_het_han ?? ""));

  const guiThem = async (action: "hoan-huy-lo" | "so-ngay-canh-bao", data: Record<string, unknown>) => {
    setDang(true);
    setLoi(null);
    const kq = await guiKho(action, data);
    setDang(false);
    if (!kq.ok) { setLoi(kq.loi); return; }
    router.refresh();
  };

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
    let soonCount = 0;
    let expiredCount = 0;
    for (const b of batches) {
      // Chỉ đếm lô còn thuốc trên kệ (`canh_bao_han` máy chủ trả).
      if (b.canh_bao_han && b.trang_thai_han === "sap_het_han") soonCount++;
      if (b.canh_bao_han && b.trang_thai_han === "het_han") expiredCount++;
    }
    return { tonTheoDonVi: tongTonTheoDonVi(batches), soonCount, expiredCount };
  }, [batches]);

  const guiLo = async () => {
    if (!lo) return;
    setDang(true);
    setLoi(null);
    const kq = await guiKho(lo.loai, lo.loai === "sua-lo" ? {
      drug_batch_id: lo.id, batch_code: lo.batch_code?.trim(), expiry_date: lo.expiry_date || null,
    } : {
      drug_batch_id: lo.id, so_luong: lo.so_luong.trim(), ly_do: lo.ly_do.trim(),
    }, lo.khoa);
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
      {cauHinhHan?.sua_canh_bao_duoc ? (
        <div className="flex flex-wrap items-end gap-2">
          <label className="block"><span className="mb-1 block text-meta text-ink-soft">Cảnh báo trước hạn (số ngày)</span><input value={ngay} inputMode="numeric" onChange={(e) => setNgay(e.target.value)} className={`${INPUT} sm:w-40`} /></label>
          <Button type="button" variant="secondary" disabled={dang || !ngay.trim()} onClick={() => void guiThem("so-ngay-canh-bao", { so_ngay: ngay })}>Lưu cảnh báo</Button>
        </div>
      ) : null}
      {loi ? <p role="alert" className="text-meta text-danger">{loi}</p> : null}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {the(batches.length, "Lô thuốc")}
        {the(tonTheoDonVi(summary.tonTheoDonVi), "Tổng tồn (theo từng đơn vị)")}
        {the(summary.soonCount, "Lô sắp hết hạn", summary.soonCount > 0 ? "text-warning" : undefined)}
        {the(summary.expiredCount, "Lô hết hạn còn trên kệ", summary.expiredCount > 0 ? "text-danger" : undefined)}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {(["all", "con_han", "sap_het_han", "het_han", "chua_co_han"] as const).map((f) => (
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
        {/* Điện thoại: bỏ Mã lô (hiện dưới tên thuốc) và Giá nhập để cột TỒN nằm trong
            màn hình, không phải vuốt ngang mới thấy (đo 17/10 ở 375px). */}
        <table className="w-full text-left text-body sm:min-w-2xl">
          <thead className={TBL_HEAD}>
            <tr>
              <th className="px-3 py-2">Thuốc</th>
              <th className="hidden px-3 py-2 sm:table-cell">Mã lô</th>
              {tachKhoQuay ? <th className="px-3 py-2">Nơi chứa</th> : null}
              <th className="px-3 py-2">Hạn dùng</th>
              <th className="px-3 py-2 text-right">Tồn</th>
              <th className="px-3 py-2">Đơn vị</th>
              <th className="hidden px-3 py-2 text-right sm:table-cell">Giá nhập</th>
              <th className="px-3 py-2">Trạng thái</th>
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody className={TBL_DIV}>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-3 py-6 text-center text-ink-muted">
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
                      <span className="block text-meta font-normal text-ink-muted sm:hidden">
                        {b.batch_code}
                      </span>
                    </td>
                    <td className="hidden px-3 py-2 text-ink-muted sm:table-cell">{b.batch_code}</td>
                    {tachKhoQuay ? (
                      <td className="px-3 py-2">
                        <Chip tone={b.noi_chua === "KHO" ? "neutral" : "success"}>
                          {b.noi_chua === "KHO" ? "KHO" : "QUẦY"}
                        </Chip>
                      </td>
                    ) : null}
                    <td className="px-3 py-2 text-ink-muted">{fmtDate(b.expiry_date)}</td>
                    <td className="px-3 py-2 text-right font-semibold tabular-nums text-ink">
                      {fmtQty(b.quantity_on_hand)}
                    </td>
                    <td className="px-3 py-2 text-ink-muted">{b.unit}</td>
                    <td className="hidden px-3 py-2 text-right tabular-nums text-ink-muted sm:table-cell">
                      {tienVnd(b.cost_price)}
                    </td>
                    <td className="px-3 py-2">
                      <Chip tone={STATE_TONE[st]}>{STATE_LABEL[st]}</Chip>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 text-right">
                      <a
                        href={`/print/tem-lo?ids=${b.id}`}
                        target="_blank"
                        rel="noopener"
                        className="inline-flex min-h-8 items-center rounded-control px-2 text-meta text-brand-700 hover:underline"
                      >
                        In tem
                      </a>
                      {ghiDuoc ? (
                        <>
                      <Button type="button" size="sm" variant="ghost" onClick={() => {
                        setLoi(null);
                        setLo({ id: b.id, loai: "sua-lo", so_luong: "", ly_do: "", batch_code: b.batch_code, expiry_date: b.expiry_date ?? "" });
                      }}>Sửa lô</Button>
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
                      {b.trang_thai_han === "het_han" && b.quantity_on_hand > 0 ? (
                        <Button type="button" size="sm" variant="danger" onClick={() => {
                          setLoi(null);
                          setLo({ id: b.id, loai: "huy-lo-het-han", so_luong: String(b.quantity_on_hand), ly_do: "", khoa: crypto.randomUUID() });
                        }}>Huỷ lô hết hạn</Button>
                      ) : null}
                      {b.huy_lo_txn_id ? (
                        <Button type="button" size="sm" variant="ghost" disabled={dang} onClick={() => void guiThem("hoan-huy-lo", { inventory_txn_id: b.huy_lo_txn_id })}>Hoàn huỷ lô</Button>
                      ) : null}
                        </>
                      ) : null}
                    </td>
                  </tr>
                );
                if (!dangMo || !lo) return [hang];
                return [
                  hang,
                  <tr key={`${b.id}-thao-tac`} className="bg-surface-muted">
                    <td colSpan={9} className="px-3 py-3">
                      <div className="flex flex-wrap items-end gap-2">
                        {lo.loai === "sua-lo" ? (
                          <>
                            <label className="block"><span className="mb-1 block text-meta text-ink-soft">Số lô</span><input value={lo.batch_code} onChange={(e) => setLo({ ...lo, batch_code: e.target.value })} className={INPUT} /></label>
                            <label className="block"><span className="mb-1 block text-meta text-ink-soft">Hạn dùng (có thể nhập sau)</span><input type="date" value={lo.expiry_date} onChange={(e) => setLo({ ...lo, expiry_date: e.target.value })} className={INPUT} /></label>
                          </>
                        ) : (
                          <>
                        <label className="block">
                          <span className="mb-1 block text-meta text-ink-soft">
                            {lo.loai === "adjust"
                              ? "Lệch kiểm kê (âm = bớt, dương = thêm)"
                              : "Số lượng huỷ"}
                          </span>
                          <input
                            value={lo.so_luong}
                            disabled={lo.loai === "huy-lo-het-han"}
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
                          </>
                        )}
                        <Button
                          type="button"
                          variant={lo.loai === "discard" || lo.loai === "huy-lo-het-han" ? "danger" : "primary"}
                          disabled={dang || (lo.loai === "sua-lo" ? !lo.batch_code?.trim() : !lo.so_luong.trim() || !lo.ly_do.trim())}
                          onClick={() => void guiLo()}
                        >
                          {dang ? "Đang lưu…" : lo.loai === "sua-lo" ? "Lưu lô" : lo.loai === "adjust" ? "Lưu điều chỉnh" : "Huỷ thuốc"}
                        </Button>
                        <Button type="button" variant="ghost" onClick={() => setLo(null)}>
                          Thôi
                        </Button>
                      </div>
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
