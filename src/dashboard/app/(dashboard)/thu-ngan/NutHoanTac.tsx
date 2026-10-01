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

export default function NutHoanTac({
  cycleId,
  soTien,
  onXong,
  quay,
  nhan = "Hoàn tác lần thu",
}: {
  cycleId: string;
  soTien?: number | null;
  onXong: (cau: string) => void;
  /** Quầy đang đứng — máy chủ chỉ hoàn tác lần thu của đúng quầy ấy (01/10/2026). */
  quay?: "dich_vu" | "thuoc";
  nhan?: string;
}) {
  const [mo, setMo] = useState(false);
  const [lyDo, setLyDo] = useState("");
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

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
      const d = (await r.json().catch(() => null)) as { message?: string; error?: string } | null;
      if (!r.ok) {
        setLoi(d?.message ?? d?.error ?? "Không hoàn tác được.");
        return;
      }
      setMo(false);
      setLyDo("");
      onXong("Đã hoàn tác lần thu — lượt về chưa thu, thu lại khi sẵn sàng.");
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
          cau={`Hoàn tác lần thu${soTien ? ` ${soTien.toLocaleString("vi-VN")}đ` : ""}? Lượt về chưa thu — trả lại tiền cho khách nếu đã nhận.`}
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
        <Button size="sm" variant="danger" className="max-sm:h-10" onClick={() => setMo(true)}>
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
