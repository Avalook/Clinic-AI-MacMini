"use client";

// CHỈ ĐỊNH CŨ CHƯA LÀM (chốt 29/10/2026, "hôm nào xong hôm đó").
//
// Check-in không còn tự kéo chỉ định từ HÔM TRƯỚC sang lượt mới. Bàn khám hiện
// chúng ở đây — tên, lượt cũ, đã đóng tiền chưa (máy chủ nói) — để bác sĩ quyết:
// [Làm hôm nay] dời chỉ định sang lượt này (tiền đi theo: đã đóng thì quầy không
// thu lại); [Hoàn tác] ở thông báo trả nó về lượt cũ. Không quyết gì thì thôi.
// Luật (cái nào hiện, dời được không, tiền) ở `chi_dinh_cu_service`.

import { useCallback, useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import ThongBaoHoanTac, { type ThongBao } from "@/components/ui/ThongBaoHoanTac";
import { fmtDate } from "@/lib/datetime";

import { useNgheBang } from "../../dung-nghe-bang";
import { docBang, guiThaoTac } from "../api";
import { lenhHoanTac } from "../hoan-tac";

interface ChiDinhCu {
  order_id: string;
  service_name: string;
  ngay_luot: string;
  da_dong_tien: boolean;
  nhan_tien: string;
}

export default function ChiDinhCuChuaLam({
  visitId,
  choGhi,
  onDaDoi,
}: {
  visitId: string;
  choGhi: boolean;
  /** Đã dời / trả về — màn nạp lại chỉ định của lượt. */
  onDaDoi: () => void;
}) {
  const [ds, setDs] = useState<ChiDinhCu[]>([]);
  const [dangGui, setDangGui] = useState<string | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [thongBao, setThongBao] = useState<ThongBao | null>(null);

  const nap = useCallback(async () => {
    const kq = await docBang<{ chi_dinh_cu: ChiDinhCu[] }>("chi-dinh-cu", { luot: visitId });
    if (kq.ok) setDs(kq.data.chi_dinh_cu);
  }, [visitId]);

  useEffect(() => {
    const t = setTimeout(() => void nap(), 0);
    return () => clearTimeout(t);
  }, [nap]);
  // Chỉ định đổi ở chỗ KHÁC (nút [Để lần sau] trên thẻ chỉ định, lần khác của
  // người khác) → khung tự nạp lại; không thì phải F5 mới thấy chỉ định quay về
  // (bấm staging 29/10/2026).
  useNgheBang(["service_order"], nap);

  const lamHomNay = async (c: ChiDinhCu) => {
    setDangGui(c.order_id);
    setLoi(null);
    const kq = await guiThaoTac("lam-hom-nay", c.order_id, { visit_id: visitId });
    setDangGui(null);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    setThongBao({
      cau: `Đã đưa "${c.service_name}" vào lượt hôm nay`,
      goi: lenhHoanTac("tra-ve-luot-cu", c.order_id, { visit_id: visitId }),
    });
    await nap();
    onDaDoi();
  };

  return (
    <>
      {ds.length > 0 ? (
        <section className="space-y-2 rounded-card border border-warning bg-warning-bg p-3">
          <h3 className="text-label font-semibold text-ink">
            Khách còn {ds.length} chỉ định cũ chưa làm
          </h3>
          <ul className="divide-y divide-hairline">
            {ds.map((c) => (
              <li key={c.order_id} className="flex flex-wrap items-center gap-2 py-2">
                <span className="min-w-0 flex-1 text-body text-ink">
                  {c.service_name}
                  <span className="text-ink-muted"> · lượt {fmtDate(c.ngay_luot)}</span>
                </span>
                <Chip tone={c.da_dong_tien ? "success" : "neutral"}>{c.nhan_tien}</Chip>
                {choGhi ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    disabled={dangGui !== null}
                    onClick={() => void lamHomNay(c)}
                  >
                    {dangGui === c.order_id ? "Đang đưa vào…" : "Làm hôm nay"}
                  </Button>
                ) : null}
              </li>
            ))}
          </ul>
          {loi ? <p className="text-label text-danger">{loi}</p> : null}
        </section>
      ) : null}
      <ThongBaoHoanTac
        thongBao={thongBao}
        onDong={() => setThongBao(null)}
        onHoanTacXong={() => {
          void nap();
          onDaDoi();
        }}
      />
    </>
  );
}
