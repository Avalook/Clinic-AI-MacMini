"use client";

// ĐẦU DÒ BIO THEO CHỈ ĐỊNH (Tuyền chốt 14/10/2026, G9 — Notion recap 12/10 mục 3:
// "sản phẩm đầu dò bio cho hiện bổ sung trong Chỉ định CLS thay vì ở bước thanh
// toán"). Bác sĩ chọn "Bio 1 lần / nhiều lần" ngay ở chỉ định siêu âm đầu dò /
// tập máy Bio. Mỗi chỉ định có gợi ý đầu dò một nhóm nút chọn MỘT (radio): Không
// dùng · Bio 1 lần · Bio nhiều lần — bấm lại là đổi, không cộng dồn.
//
// Máy chủ quyết tất cả (`GET /luot-kham/visits/{id}/dau-do`, `POST /luot-kham/
// orders/{id}/dau-do`): chỉ định nào có gợi ý, hàng nào chọn được (bán được, không
// cần quản lý duyệt), ai chọn được (quyền chỉ định), khoá khi đã thu. Tiền đi theo
// chỉ định: bỏ chỉ định / khách không làm thì đầu dò không tính; thu cùng hoá đơn
// dịch vụ. Quầy thu vẫn bỏ được đầu dò trước khi thu (bắt ghi lý do).

import { useCallback, useEffect, useState } from "react";

import ChipChon from "@/components/ui/ChipChon";
import Chip from "@/components/ui/Chip";
import type { DauDoChiDinhGoi } from "@/lib/vat-tu";

import { docBang, guiThaoTac } from "../api";
import { useNgheBang } from "../../dung-nghe-bang";

const tien = (n: number) => `${new Intl.NumberFormat("vi-VN").format(n)}đ`;

export default function DauDoChiDinh({
  visitId,
  orderIds,
  choGhi,
  onDoi,
}: {
  visitId: string;
  /** Các chỉ định đang hiện ở thẻ bên dưới — chỉ vẽ đầu dò cho đúng những cái này. */
  orderIds: readonly string[];
  choGhi: boolean;
  /** Gọi sau mỗi lần lưu xong (quầy / phiếu đọc lại tiền). */
  onDoi?: () => void;
}) {
  const [goi, setGoi] = useState<DauDoChiDinhGoi | null>(null);
  const [dangGui, setDangGui] = useState<string | null>(null);
  const [loi, setLoi] = useState<{ id: string; loi: string } | null>(null);

  const nap = useCallback(async () => {
    const kq = await docBang<DauDoChiDinhGoi>("dau-do", { luot: visitId });
    if (kq.ok) setGoi(kq.data);
  }, [visitId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void nap();
  }, [nap]);

  // Quầy bỏ / thêm đầu dò, chỉ định bị bỏ / khôi phục → cập nhật liền.
  useNgheBang(["luot_vat_tu", "service_order"], () => void nap());

  async function chon(orderId: string, servicePriceId: string | null) {
    setDangGui(orderId);
    setLoi(null);
    try {
      const kq = await guiThaoTac("dau-do-chon", orderId, {
        service_price_id: servicePriceId,
        so_luong: 1,
      });
      if (!kq.ok) {
        setLoi({ id: orderId, loi: kq.loi });
        return;
      }
      const moi = kq.data as unknown as Pick<DauDoChiDinhGoi, "chi_dinh">;
      setGoi((cu) => (cu ? { ...cu, chi_dinh: moi.chi_dinh } : cu));
      onDoi?.();
    } finally {
      setDangGui(null);
    }
  }

  const hang = (goi?.chi_dinh ?? []).filter((c) => orderIds.includes(c.order_id));
  if (!goi || hang.length === 0) return null;
  const sua = choGhi && goi.duoc_sua;

  return (
    <section aria-label="Đầu dò theo chỉ định" className="space-y-2 rounded-card border border-hairline bg-surface p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-body font-semibold text-ink">Đầu dò kèm chỉ định</h3>
        <span className="text-meta text-ink-muted">
          Tiền đầu dò thu cùng dịch vụ · bỏ chỉ định thì đầu dò bỏ theo
        </span>
      </div>
      <ul className="space-y-3">
        {hang.map((c) => {
          const daChon = c.da_chon;
          const khoa = c.khoa_quan_ly || !sua || dangGui !== null || Boolean(daChon?.da_thu);
          const trongGoiY = daChon ? c.goi_y.some((g) => g.service_price_id === daChon.service_price_id) : true;
          return (
            <li key={c.order_id} className="space-y-1.5">
              <p className="text-body text-ink">{c.ten}</p>
              {c.khoa_quan_ly ? (
                <p role="status" className="text-meta text-ink-muted">
                  Đầu dò của chỉ định này cần Quản lý xử lý. Vui lòng liên hệ Quản lý.
                </p>
              ) : (
                <div role="radiogroup" aria-label={`Đầu dò — ${c.ten}`} className="flex flex-wrap gap-2">
                  <ChipChon
                    kieu="mot"
                    ten={`dau-do-${c.order_id}`}
                    chon={!daChon}
                    disabled={khoa}
                    onDoi={() => void chon(c.order_id, null)}
                  >
                    Không dùng đầu dò
                  </ChipChon>
                  {c.goi_y.map((g) => (
                    <ChipChon
                      key={g.service_price_id}
                      kieu="mot"
                      ten={`dau-do-${c.order_id}`}
                      chon={daChon?.service_price_id === g.service_price_id}
                      disabled={khoa}
                      onDoi={() => void chon(c.order_id, g.service_price_id)}
                    >
                      {g.ten} · {tien(g.don_gia)}
                    </ChipChon>
                  ))}
                  {daChon && !trongGoiY ? (
                    <ChipChon kieu="mot" ten={`dau-do-${c.order_id}`} chon disabled onDoi={() => undefined}>
                      {daChon.ten} · {tien(daChon.don_gia)}
                    </ChipChon>
                  ) : null}
                </div>
              )}
              {daChon?.da_thu ? (
                <p className="flex flex-wrap items-center gap-2 text-meta text-ink-muted">
                  <Chip tone="success">Đã thu</Chip>
                  Muốn đổi thì quầy thu “Hoàn tác lần thu” trước.
                </p>
              ) : null}
              {!c.chon_lam ? (
                <p className="text-meta text-ink-muted">
                  Khách không chọn làm dịch vụ này — đầu dò không tính tiền.
                </p>
              ) : null}
              {loi?.id === c.order_id ? (
                <p role="alert" className="text-meta text-danger">
                  {loi.loi}
                </p>
              ) : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
