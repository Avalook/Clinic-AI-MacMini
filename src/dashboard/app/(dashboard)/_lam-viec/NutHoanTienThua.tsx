"use client";

// NÚT HOÀN TIỀN THỪA (G4d, R6 — Tuyền chốt B 14/10/2026): máy hoàn ĐÚNG số còn
// thừa, mặc định THEO HÌNH THỨC KHÁCH ĐÃ TRẢ của từng lần thu gốc; người bấm
// đổi được (khách trả CK nhưng muốn nhận tiền mặt…). Trước đây luôn tiền mặt →
// khách CK mà két ghi trả TM, lệch két.
//
// Máy chủ quyết số tiền và hình thức mặc định; màn chỉ vẽ và gửi lựa chọn.
// Dùng chung ở hộp check-out (`KhoanNoKhiVe`) và quầy thu (`QuayThuNgan`).

import { useState } from "react";

import Button from "@/components/ui/Button";
import OChon from "@/components/ui/OChon";
import { loiDocDuoc } from "@/lib/loi-doc-duoc";

type HinhThuc = "CASH" | "TRANSFER" | "QR";

const NHAN: Record<string, string> = {
  CASH: "tiền mặt",
  TRANSFER: "chuyển khoản",
  QR: "QR",
};

const tien = (n: number | null | undefined) =>
  `${Math.round(n ?? 0).toLocaleString("vi-VN")}đ`;

export default function NutHoanTienThua({
  visitId,
  tong,
  theoHinhThuc,
  nhan = "Đã hoàn cho khách — hoàn",
  onDoi,
}: {
  visitId: string;
  tong: number;
  /** Số thừa theo hình thức khách đã trả (máy chủ tính); thiếu = chưa biết. */
  theoHinhThuc?: Record<string, number> | null;
  nhan?: string;
  onDoi: () => void;
}) {
  const [hinhThuc, setHinhThuc] = useState<HinhThuc | "">("");
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  const theoGoc = Object.entries(theoHinhThuc ?? {}).filter(([, v]) => v > 0);
  const moTa = hinhThuc
    ? `${tien(tong)} ${NHAN[hinhThuc]}`
    : theoGoc.length > 0
      ? theoGoc.map(([k, v]) => `${tien(v)} ${NHAN[k] ?? k}`).join(" · ")
      : `${tien(tong)} theo hình thức khách đã trả`;
  const coChuyenKhoan = hinhThuc
    ? hinhThuc !== "CASH"
    : theoGoc.length === 0 || theoGoc.some(([k]) => k !== "CASH");

  async function hoan() {
    setDang(true);
    setLoi(null);
    try {
      const r = await fetch("/api/reception/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          hanh_dong: "hoan_tien_thua",
          visit_id: visitId,
          hinh_thuc: hinhThuc || null,
        }),
      });
      const d = (await r.json().catch(() => null)) as { ok?: boolean } | null;
      if (!r.ok || !d?.ok) setLoi(loiDocDuoc(d, `Chưa hoàn được (HTTP ${r.status}).`));
      else onDoi();
    } catch {
      setLoi("Mất kết nối — chưa hoàn.");
    } finally {
      setDang(false);
    }
  }

  return (
    <div className="space-y-1">
      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" size="sm" variant="primary" disabled={dang} onClick={() => void hoan()}>
          {dang ? "Đang hoàn…" : `${nhan} ${moTa}`}
        </Button>
        <label className="flex items-center gap-1 text-meta text-ink-muted">
          Hình thức
          <OChon
            value={hinhThuc}
            disabled={dang}
            onChange={(e) => setHinhThuc(e.target.value as HinhThuc | "")}
            aria-label="Hình thức hoàn tiền thừa"
          >
            <option value="">Như khách đã trả</option>
            <option value="CASH">Tiền mặt</option>
            <option value="TRANSFER">Chuyển khoản</option>
          </OChon>
        </label>
      </div>
      {coChuyenKhoan ? (
        <p className="text-meta text-ink-muted">
          Hoàn chuyển khoản là khoản “Chờ chuyển”: chuyển xong thì xác nhận kèm mã giao dịch ở mục
          Hoàn tiền của phiếu thu.
        </p>
      ) : null}
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </div>
  );
}
