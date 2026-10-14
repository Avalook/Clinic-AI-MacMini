"use client";

// KHOÁ SỔ THEO CA (G4c — Tuyền chốt A, 14/10/2026).
//
// Chỉ hiện khi máy chủ báo đang xem ĐÚNG một ca (`xem_mot_ca`: một ngày, một ca,
// một cơ sở, cả hai loại tiền). Chưa chốt → "Chốt ca"; đã chốt → số trên màn là
// số LÚC CHỐT, kèm phần phát sinh sau chốt (máy chủ tính) và "Mở khoá" cho Quản
// lý (bắt lý do). Không khoá cứng: mở khoá xong chốt lại được.
// Màn không tính gì — mọi số, quyền, khoá trùng do máy chủ quyết.

import { useState } from "react";

import Button from "@/components/ui/Button";
import XacNhanTaiCho from "@/components/ui/XacNhanTaiCho";
import { loiDocDuoc } from "@/lib/loi-doc-duoc";

import { INPUT } from "../form-ui";

export interface ChotCa {
  id: string;
  ngay: string;
  ca: string;
  chot_luc: string;
  chot_boi: string | null;
  ghi_chu: string | null;
}

type OTien = { thu: number; huy: number; hoan: number; thuc_thu: number };

const tien = (n: number) => `${n.toLocaleString("vi-VN")}đ`;
const gio = (v: string) =>
  new Date(v).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh", hour12: false });

export default function KhoiChotCa({
  xemMotCa,
  chot,
  sauChot,
  dieuChinh,
  ngay,
  ca,
  coSo,
  quanLy,
  onDoi,
}: {
  xemMotCa: boolean;
  chot: ChotCa | null;
  sauChot: OTien | null;
  dieuChinh: { so_phieu: number; tong: number } | null;
  ngay: string;
  ca: string;
  coSo: string;
  quanLy: boolean;
  onDoi: () => void;
}) {
  const [mo, setMo] = useState<"chot" | "mo_khoa" | null>(null);
  const [chu, setChu] = useState("");
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  async function gui(than: Record<string, unknown>) {
    setDang(true);
    setLoi(null);
    try {
      const r = await fetch("/api/reports/chot-ca", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(than),
      });
      const d = (await r.json().catch(() => null)) as { ok?: boolean } | null;
      if (!r.ok || !d?.ok) {
        setLoi(loiDocDuoc(d, `Chưa lưu được (HTTP ${r.status}).`));
        return;
      }
      setMo(null);
      setChu("");
      onDoi();
    } catch {
      setLoi("Mất kết nối — chưa lưu.");
    } finally {
      setDang(false);
    }
  }

  const coSauChot = !!sauChot && (sauChot.thu !== 0 || sauChot.huy !== 0 || sauChot.hoan !== 0);
  return (
    <section aria-label="Chốt sổ ca" className="space-y-2 print:hidden">
      {dieuChinh && dieuChinh.so_phieu > 0 ? (
        <p className="rounded-control bg-warning-bg px-3 py-2 text-meta text-warning">
          Điều chỉnh ca trước: {dieuChinh.so_phieu} phiếu của ca ĐÃ CHỐT bị huỷ trong khoảng này (
          {tien(dieuChinh.tong)}) — đã tính vào “Trả lại”, số của ca cũ giữ nguyên.
        </p>
      ) : null}
      {!xemMotCa ? null : chot ? (
        <div className="space-y-2 rounded-control border border-line bg-surface-muted px-3 py-2">
          <p className="text-body text-ink">
            <span className="font-semibold">Đã chốt ca</span> lúc {gio(chot.chot_luc)}
            {chot.chot_boi ? ` · ${chot.chot_boi}` : ""} — số dưới đây là số LÚC CHỐT.
            {chot.ghi_chu ? ` Ghi chú: “${chot.ghi_chu}”.` : ""}
          </p>
          {coSauChot && sauChot ? (
            <p className="text-meta text-warning">
              Sau khi chốt có thêm: thu {tien(sauChot.thu)} · huỷ {tien(sauChot.huy)} · hoàn{" "}
              {tien(sauChot.hoan)} (thực thu {tien(sauChot.thuc_thu)}) — huỷ / hoàn tác sau chốt
              tính vào ca đang làm.
            </p>
          ) : null}
          <p className="text-meta text-ink-muted">
            Báo cáo gộp nhiều ngày tính lại từ số sống: tổng tiền khớp, nhưng nếu có “Đổi hình
            thức” sau khi chốt thì phần chia Tiền mặt / Chuyển khoản của ngày cũ theo hình thức mới.
          </p>
          {quanLy ? (
            mo === "mo_khoa" ? (
              <XacNhanTaiCho
                cau="Mở khoá ca này? Số đã chốt được giữ lại trong nhật ký; mở xong chốt lại được."
                nhanDongY="Mở khoá"
                onDongY={() => void gui({ hanh_dong: "mo_khoa", id: chot.id, ly_do: chu })}
                onThoi={() => setMo(null)}
                dangGui={dang}
                choDongY={chu.trim().length >= 3}
              >
                <input
                  value={chu}
                  onChange={(e) => setChu(e.target.value)}
                  maxLength={500}
                  placeholder="Lý do mở khoá (bắt buộc)"
                  aria-label="Lý do mở khoá ca"
                  className={INPUT}
                />
              </XacNhanTaiCho>
            ) : (
              <Button type="button" size="sm" variant="secondary" onClick={() => setMo("mo_khoa")}>
                Mở khoá ca
              </Button>
            )
          ) : null}
        </div>
      ) : mo === "chot" ? (
        <XacNhanTaiCho
          cau="Chốt ca này? Số báo cáo hiện tại được giữ nguyên; huỷ / hoàn tác sau đó tính vào ca đang làm."
          nhanDongY="Chốt ca"
          onDongY={() => void gui({ hanh_dong: "chot", ngay, ca, co_so: coSo, ghi_chu: chu })}
          onThoi={() => setMo(null)}
          dangGui={dang}
        >
          <input
            value={chu}
            onChange={(e) => setChu(e.target.value)}
            maxLength={500}
            placeholder="Ghi chú (không bắt buộc) — vd: két đủ, đã bàn giao"
            aria-label="Ghi chú chốt ca"
            className={INPUT}
          />
        </XacNhanTaiCho>
      ) : (
        <Button type="button" size="lg" variant="primary" onClick={() => setMo("chot")}>
          Chốt ca
        </Button>
      )}
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </section>
  );
}
