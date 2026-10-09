"use client";

// Lượt bán lẻ: ĐƠN GẦN NHẤT của khách cũ + "Bán theo đơn này" (09/10/2026).
//
// Máy chủ chọn đơn, tính số kê / đã mua / còn lại và soạn sẵn lời nhắc
// (`ban_theo_don_service`); ở đây chỉ vẽ và gửi hai lệnh: nối đơn (thêm dòng số
// còn lại vào "Lấy thêm thuốc" bên dưới) · gỡ nối (hoàn tác, khi chưa thu).
// Lời nhắc chỉ để đọc — không nút nào bị khoá vì nó.

import { useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";

import { fmtNgay } from "./ban-thuoc";
import { CHAM } from "./DongThuoc";

export interface DongDonGoc {
  drug_catalog_id: string | null;
  ten: string;
  ten_bac_si: string | null;
  don_vi: string | null;
  so_ke: string | null;
  da_mua: string;
  dang_ban: string;
  con_lai: string | null;
  vuot: boolean;
}

export interface DonGoc {
  visit_id: string;
  ngay_kham: string | null;
  bac_si: string | null;
  ngay_hen: string | null;
  da_noi: boolean;
  dong: DongDonGoc[];
  nhac: string[];
}

async function gui(duong: string, than: Record<string, string>) {
  try {
    const r = await fetch(`/api/pharmacy/${duong}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(than),
    });
    const d = (await r.json().catch(() => null)) as {
      message?: string;
      error?: string;
      so_dong_them?: number;
      bo_qua?: string[];
    } | null;
    if (!r.ok) return { loi: d?.message ?? d?.error ?? `Không ghi được (HTTP ${r.status}).` };
    return { d };
  } catch {
    return { loi: "Mất kết nối — CHƯA ghi được." };
  }
}

export default function DonGanNhat({
  visitId,
  don,
  choSua,
  onDoi,
}: {
  visitId: string;
  don: DonGoc;
  /** Tiền thuốc chưa thu / chưa chờ xác minh — mới nối / gỡ được. */
  choSua: boolean;
  onDoi: (cau: string | null, loi: string | null) => void | Promise<void>;
}) {
  const [dang, setDang] = useState(false);

  const banTheoDon = async () => {
    setDang(true);
    const kq = await gui("ban-le-theo-don", { visit_id: visitId, don_goc_visit_id: don.visit_id });
    setDang(false);
    if (kq.loi) return void (await onDoi(null, kq.loi));
    const so = kq.d?.so_dong_them ?? 0;
    const boQua = kq.d?.bo_qua ?? [];
    await onDoi(
      [
        so > 0
          ? `Đã thêm ${so} thuốc theo đơn — số điền sẵn là số còn lại, sửa được ở dưới.`
          : "Đã nối đơn — không có thuốc nào cần thêm.",
        ...boQua,
      ].join(" "),
      null,
    );
  };

  const goNoi = async () => {
    setDang(true);
    const kq = await gui("ban-le-go-don", { visit_id: visitId });
    setDang(false);
    if (kq.loi) return void (await onDoi(null, kq.loi));
    await onDoi(
      "Đã gỡ nối đơn. Các dòng thuốc đã thêm vẫn còn — bỏ tick nếu khách không lấy.",
      null,
    );
  };

  return (
    <section aria-label="Đơn gần nhất" className="space-y-2 border-b border-line px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-body font-semibold text-ink">
          {don.da_noi ? "Đang bán theo đơn" : "Đơn gần nhất"}
        </h3>
        {don.da_noi ? <Chip tone="brand">Đã nối đơn</Chip> : null}
      </div>
      <p className="text-meta text-ink-muted">
        {[
          don.ngay_kham ? `Khám ${fmtNgay(don.ngay_kham)}` : null,
          don.bac_si ? `BS ${don.bac_si}` : null,
          don.ngay_hen ? `Hẹn tái khám ${fmtNgay(don.ngay_hen)}` : "Không có hẹn tái khám",
        ]
          .filter(Boolean)
          .join(" · ")}
      </p>

      {don.nhac.length > 0 ? (
        <ul role="status" className="space-y-1 rounded-control bg-warning-bg px-3 py-2">
          {don.nhac.map((c) => (
            <li key={c} className="text-meta text-warning">
              {c}
            </li>
          ))}
        </ul>
      ) : null}

      <ul className="divide-y divide-line rounded-control border border-line">
        {don.dong.map((d) => (
          <li
            key={d.drug_catalog_id ?? d.ten}
            className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2"
          >
            <span className="min-w-0 flex-1 basis-40">
              <span className="block text-body font-medium text-ink">{d.ten}</span>
              {d.ten_bac_si ? (
                <span className="block text-meta text-ink-muted">BS ghi: {d.ten_bac_si}</span>
              ) : null}
              {d.drug_catalog_id ? null : (
                <span className="block text-meta text-ink-muted">Chưa xác định thuốc kho</span>
              )}
            </span>
            <span className="text-meta tabular-nums text-ink-soft">
              Kê {d.so_ke ?? "—"} · Đã mua {d.da_mua}
              {d.dang_ban !== "0" ? ` · Đang bán ${d.dang_ban}` : ""} · Còn {d.con_lai ?? "—"}
              {d.don_vi ? ` ${d.don_vi}` : ""}
            </span>
            {d.vuot ? <Chip tone="warning">Vượt số kê</Chip> : null}
          </li>
        ))}
      </ul>

      {choSua ? (
        <div className="flex flex-wrap gap-2">
          {don.da_noi ? (
            <Button
              type="button"
              className={CHAM}
              size="sm"
              variant="secondary"
              disabled={dang}
              onClick={() => void goNoi()}
            >
              Gỡ nối đơn
            </Button>
          ) : (
            <Button
              type="button"
              className={CHAM}
              size="sm"
              variant="soft"
              disabled={dang}
              onClick={() => void banTheoDon()}
            >
              {dang ? "Đang thêm…" : "Bán theo đơn này"}
            </Button>
          )}
        </div>
      ) : null}
    </section>
  );
}
