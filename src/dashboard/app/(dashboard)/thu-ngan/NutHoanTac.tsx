"use client";

// HOÀN TÁC LẦN THU (Tuyền 01/10/2026: "tất cả đều có nút hoàn tác để nhân viên
// làm lại thao tác bị sai, và phải cập nhật tới tất cả các nơi").
//
// MỘT nút cho mọi lần thu (dịch vụ, thuốc, phụ thu nằm trong hoá đơn dịch vụ):
// máy chủ chọn đúng lệnh — đã thu → huỷ phiếu; chuyển khoản chờ xác minh → huỷ
// lần chờ (`POST /api/payment {action:"hoan-tac"}` → `PaymentService.hoan_tac`).
// Lượt về CHƯA THU; mọi màn tự cập nhật qua tin SSE của `payment_cycle`.
//
// KHÁC HOÀN TIỀN: hoàn tác = thu nhầm, trả lại ngay (như chưa từng thu); hoàn
// tiền = khách đã trả đúng, giờ trả lại (phiếu thu vẫn đứng) — nút "Hoàn tiền".
// Lý do không bắt buộc; ai / lúc nào máy chủ tự ghi.

import { useState } from "react";

import Button from "@/components/ui/Button";
import XacNhanTaiCho from "@/components/ui/XacNhanTaiCho";

/** Máy chủ tính: số phải trả khách = đã thu − đã hoàn, không phải nguyên tổng phiếu. */
interface XemTruoc {
  da_thu: number;
  da_hoan: number;
  phai_tra: number;
  thuoc_ve_quay: number | string;
  co_hoan_cho: boolean;
  co_hoa_don_cong_ty: boolean;
  da_xuat_misa: boolean;
}

function cauHoi(x: XemTruoc | null): string {
  if (!x) return "Hoàn tác lần thu này? Lượt về chưa thu.";
  const ve = Number(x.thuoc_ve_quay);
  const phan = [
    x.phai_tra > 0
      ? `Phải trả khách ${x.phai_tra.toLocaleString("vi-VN")}đ${
          x.da_hoan > 0 ? ` (đã thu ${x.da_thu.toLocaleString("vi-VN")}đ, đã hoàn ${x.da_hoan.toLocaleString("vi-VN")}đ)` : ""
        }.`
      : x.da_thu > 0
        ? "Đã hoàn đủ tiền, không phải trả thêm."
        : "Chưa nhận tiền, không phải trả khách.",
    ve > 0 ? "Thuốc đã giao tự về quầy — khách đã mang đi thì nhận lại thuốc." : "",
    x.co_hoa_don_cong_ty ? "Phiếu này có hoá đơn công ty — báo kế toán xử lý hoá đơn." : "",
    x.da_xuat_misa ? "Phiếu này đã xuất sang MISA — báo kế toán điều chỉnh bên MISA." : "",
  ];
  return `Hoàn tác lần thu? Lượt về chưa thu. ${phan.filter(Boolean).join(" ")}`;
}

export default function NutHoanTac({
  cycleId,
  onXong,
  quay,
  nhan = "Hoàn tác lần thu",
}: {
  cycleId: string;
  onXong: (cau: string) => void;
  /** Quầy đang đứng — máy chủ chỉ hoàn tác lần thu của đúng quầy ấy (01/10/2026). */
  quay?: "dich_vu" | "thuoc";
  nhan?: string;
}) {
  const [mo, setMo] = useState(false);
  const [xem, setXem] = useState<XemTruoc | null>(null);
  const [lyDo, setLyDo] = useState("");
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  async function moHoi() {
    setLoi(null);
    setXem(null);
    setMo(true);
    // Đọc hỏng thì vẫn hỏi được — câu không nêu số, không đoán từ tổng phiếu.
    const r = await fetch(`/api/payment?hoanTac=${cycleId}`, { cache: "no-store" }).catch(() => null);
    if (r?.ok) setXem((await r.json().catch(() => null)) as XemTruoc | null);
  }

  async function lam() {
    setDang(true);
    setLoi(null);
    try {
      const r = await fetch("/api/payment", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "hoan-tac",
          paymentCycleId: cycleId,
          lyDo: lyDo.trim() || null,
          ...(quay ? { quay } : {}),
        }),
      });
      const d = (await r.json().catch(() => null)) as {
        message?: string;
        error?: string;
        /** Khách đã về, dịch vụ đã làm → máy tự ghi nợ chờ xử lý (G4d · D). */
        tu_ghi_no?: { so_tien: number } | null;
        /** Thuốc đã giao tự về quầy (31/10/2026). */
        thuoc_ve_quay?: { so_luong: number | string } | null;
      } | null;
      if (!r.ok) {
        setLoi(d?.message ?? d?.error ?? "Không hoàn tác được.");
        return;
      }
      setMo(false);
      setLyDo("");
      onXong(
        d?.tu_ghi_no
          ? `Đã hoàn tác lần thu. Khách đã về mà dịch vụ đã làm — máy đã ghi nợ ${d.tu_ghi_no.so_tien.toLocaleString("vi-VN")}đ (chờ thu hoặc miễn), xem ở "Khách còn nợ".`
          : Number(d?.thuoc_ve_quay?.so_luong ?? 0) > 0
            ? "Đã hoàn tác lần thu — thuốc đã giao về quầy, lượt về chưa thu; thu lại rồi giao lại."
            : "Đã hoàn tác lần thu — lượt về chưa thu, thu lại khi sẵn sàng.",
      );
    } catch {
      setLoi("Mất kết nối — CHƯA hoàn tác được.");
    } finally {
      setDang(false);
    }
  }

  return (
    <div className="space-y-1">
      {mo ? (
        <XacNhanTaiCho
          cau={cauHoi(xem)}
          nhanDongY="Hoàn tác"
          onDongY={() => void lam()}
          onThoi={() => setMo(false)}
          dangGui={dang}
        >
          <input
            value={lyDo}
            onChange={(e) => setLyDo(e.target.value)}
            maxLength={500}
            placeholder="Lý do (không bắt buộc) — vd thu nhầm hình thức"
            aria-label="Lý do hoàn tác (không bắt buộc)"
            className="min-h-10 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink sm:min-h-8"
          />
        </XacNhanTaiCho>
      ) : (
        <Button size="sm" variant="danger" className="max-sm:h-10" onClick={() => void moHoi()}>
          {nhan}
        </Button>
      )}
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </div>
  );
}
