"use client";

// HOÀN TIỀN trên đúng một lần thu (contract tiền–thuốc CP5, 19/09/2026).
//
// Hoàn tiền là tiền thật trả lại khách — KHÔNG phải huỷ phiếu, KHÔNG nhả thuốc.
// Chọn dòng của hoá đơn đã thu và số lượng; SỐ TIỀN DO MÁY CHỦ TÍNH theo đơn giá
// đã thu, màn này không nhân. Chuyển khoản / QR: chờ → xác nhận có mã giao dịch,
// hoặc ghi không thành / huỷ yêu cầu.
//
// Ai được hoàn: tạm thời chỉ Quản lý (HOLD J4, chờ phòng khám chốt) — máy chủ
// báo `coQuyenHoan`; không có quyền thì chỉ xem trạng thái.

import { useState } from "react";

import Button from "@/components/ui/Button";
import StatusChip, { type StatusTone } from "@/components/ui/StatusChip";

export interface KhoanHoan {
  refund_id: string;
  amount: number;
  status: "PENDING" | "COMPLETED" | "FAILED" | "CANCELLED";
  method: "CASH" | "TRANSFER" | "QR";
  reason: string;
  reference: string | null;
  created_at: string;
  closed_reason: string | null;
  sau_khi_dong_luot: boolean;
}

export interface DongHoanDuoc {
  payment_bill_line_id: string;
  ten: string;
  so_luong: number;
  don_vi: string | null;
  da_hoan: number;
  con_hoan: number;
}

export interface HoanCuaLanThu {
  khoan_hoan: KhoanHoan[];
  dong_hoan_duoc: DongHoanDuoc[];
}

const TRANG_THAI: Record<KhoanHoan["status"], { nhan: string; tone: StatusTone }> = {
  PENDING: { nhan: "Chờ chuyển", tone: "assigned" },
  COMPLETED: { nhan: "Đã hoàn", tone: "completed" },
  FAILED: { nhan: "Không thành", tone: "blocked" },
  CANCELLED: { nhan: "Đã huỷ yêu cầu", tone: "cancelled" },
};
const TEN_PT: Record<string, string> = { CASH: "tiền mặt", TRANSFER: "chuyển khoản", QR: "QR" };
const O = "min-h-10 rounded-control border border-line bg-surface px-3 text-sm text-ink";

async function goi(body: Record<string, unknown>): Promise<string | null> {
  const r = await fetch("/api/payment", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (r.ok) return null;
  const d = (await r.json().catch(() => null)) as { message?: string; error?: string } | null;
  return d?.message ?? d?.error ?? "Không lưu được. Thử lại giúp em.";
}

export default function HoanTien({
  paymentCycleId,
  visitId,
  kind,
  hoan,
  coQuyenHoan,
  onXong,
}: {
  paymentCycleId: string;
  visitId: string;
  kind: string;
  hoan: HoanCuaLanThu;
  coQuyenHoan: boolean;
  onXong: () => void;
}) {
  const [mo, setMo] = useState(false);
  const [so, setSo] = useState<Record<string, string>>({});
  const [pt, setPt] = useState<"CASH" | "TRANSFER" | "QR">("CASH");
  const [lyDo, setLyDo] = useState("");
  const [ma, setMa] = useState<Record<string, string>>({});
  const [lyDoDong, setLyDoDong] = useState<Record<string, string>>({});
  const [dangGui, setDangGui] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  const conHoan = hoan.dong_hoan_duoc.filter((d) => d.con_hoan > 0);
  const chon = conHoan
    .map((d) => ({ payment_bill_line_id: d.payment_bill_line_id, so_luong: Number(so[d.payment_bill_line_id] || 0) }))
    .filter((d) => d.so_luong > 0);

  async function lam(body: Record<string, unknown>) {
    setDangGui(true);
    setLoi(null);
    try {
      const l = await goi(body);
      if (l) {
        setLoi(l);
        return;
      }
      setMo(false);
      setSo({});
      setLyDo("");
      onXong();
    } finally {
      setDangGui(false);
    }
  }

  if (hoan.khoan_hoan.length === 0 && (!coQuyenHoan || conHoan.length === 0)) return null;

  return (
    <div className="mt-2 space-y-2 border-t border-line pt-2">
      {hoan.khoan_hoan.map((k) => (
        <div key={k.refund_id} className="space-y-1">
          <div className="flex flex-wrap items-center gap-2 text-xs text-ink-soft">
            <StatusChip tone={TRANG_THAI[k.status].tone} label={TRANG_THAI[k.status].nhan} />
            <span>
              Hoàn <b className="text-ink">{Number(k.amount).toLocaleString("vi-VN")} đ</b> ·{" "}
              {TEN_PT[k.method]}
              {k.reference ? ` · mã GD ${k.reference}` : ""} · {k.reason}
              {k.closed_reason ? ` · ${k.closed_reason}` : ""}
            </span>
          </div>
          {k.sau_khi_dong_luot ? (
            <p className="text-xs text-ink-muted">Phát sinh SAU khi đóng lượt — lượt không mở lại.</p>
          ) : null}
          {coQuyenHoan && k.status === "PENDING" ? (
            <div className="flex flex-wrap items-end gap-2">
              <input
                aria-label="Mã giao dịch hoàn tiền"
                placeholder="Mã giao dịch ngân hàng"
                value={ma[k.refund_id] ?? ""}
                onChange={(e) => setMa((s) => ({ ...s, [k.refund_id]: e.target.value }))}
                className={O}
              />
              <Button
                size="sm"
                className="max-sm:h-10"
                disabled={dangGui || (ma[k.refund_id] ?? "").trim().length < 3}
                onClick={() => lam({ action: "hoan-tien-xac-nhan", refundId: k.refund_id, reference: ma[k.refund_id] })}
              >
                Đã chuyển xong
              </Button>
              <input
                aria-label="Lý do đóng khoản hoàn"
                placeholder="Lý do (không thành / huỷ yêu cầu)"
                value={lyDoDong[k.refund_id] ?? ""}
                onChange={(e) => setLyDoDong((s) => ({ ...s, [k.refund_id]: e.target.value }))}
                className={O}
              />
              {(["FAILED", "CANCELLED"] as const).map((tt) => (
                <Button
                  key={tt}
                  size="sm"
                  variant={tt === "FAILED" ? "danger" : "ghost"}
                  className="max-sm:h-10"
                  disabled={dangGui || (lyDoDong[k.refund_id] ?? "").trim().length < 5}
                  onClick={() =>
                    lam({ action: "hoan-tien-dong", refundId: k.refund_id, trangThai: tt, reason: lyDoDong[k.refund_id] })
                  }
                >
                  {tt === "FAILED" ? "Không thành" : "Huỷ yêu cầu"}
                </Button>
              ))}
            </div>
          ) : null}
        </div>
      ))}

      {coQuyenHoan && conHoan.length > 0 ? (
        mo ? (
          <div className="space-y-2 rounded-control bg-surface-muted p-2">
            {conHoan.map((d) => (
              <label key={d.payment_bill_line_id} className="flex flex-wrap items-center gap-2 text-xs text-ink-soft">
                <span className="min-w-0 flex-1">
                  {d.ten} — đã thu {d.so_luong} {d.don_vi ?? ""}, còn hoàn được {d.con_hoan}
                </span>
                <input
                  type="number"
                  min="0"
                  max={d.con_hoan}
                  step="any"
                  aria-label={`Số hoàn ${d.ten}`}
                  value={so[d.payment_bill_line_id] ?? ""}
                  onChange={(e) => setSo((s) => ({ ...s, [d.payment_bill_line_id]: e.target.value }))}
                  className={`${O} w-24`}
                />
              </label>
            ))}
            <div className="flex flex-wrap items-end gap-2">
              <select
                aria-label="Phương thức hoàn"
                value={pt}
                onChange={(e) => setPt(e.target.value as "CASH" | "TRANSFER" | "QR")}
                className={O}
              >
                <option value="CASH">Tiền mặt (trả ngay)</option>
                <option value="TRANSFER">Chuyển khoản (chờ xác nhận)</option>
                <option value="QR">QR (chờ xác nhận)</option>
              </select>
              <input
                aria-label="Lý do hoàn tiền"
                placeholder="Lý do hoàn (tối thiểu 5 ký tự)"
                value={lyDo}
                onChange={(e) => setLyDo(e.target.value)}
                className={`${O} min-w-0 flex-1`}
              />
            </div>
            <p className="text-xs text-ink-muted">
              Số tiền do máy chủ tính theo đơn giá đã thu. Hoàn tiền không tự nhả thuốc chưa giao — việc
              đó ở màn Nhà thuốc.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="primary"
                size="sm"
                className="max-sm:h-10"
                disabled={dangGui || chon.length === 0 || lyDo.trim().length < 5}
                onClick={() =>
                  lam({
                    action: "hoan-tien",
                    paymentCycleId,
                    visitId,
                    kind,
                    method: pt,
                    reason: lyDo,
                    dong: chon,
                  })
                }
              >
                Ghi hoàn tiền
              </Button>
              <Button size="sm" variant="ghost" className="max-sm:h-10" onClick={() => setMo(false)}>
                Thôi
              </Button>
            </div>
          </div>
        ) : (
          <Button size="sm" variant="secondary" className="max-sm:h-10" onClick={() => setMo(true)}>
            Hoàn tiền
          </Button>
        )
      ) : null}
      {loi ? (
        <p role="alert" className="text-xs text-danger">
          {loi}
        </p>
      ) : null}
    </div>
  );
}
