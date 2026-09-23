"use client";

// Mục C — KẾT QUẢ CẬN LÂM SÀNG theo từng chỉ định của lượt.
//
// Gắn bằng `service_order_id` (máy chủ đã nối). Hai chỉ định cùng tên là hai
// dòng riêng, kết quả không bao giờ chạy sang nhau. Tên dịch vụ chỉ để đọc.
//
// Hai lớp trạng thái đứng cạnh nhau, không gộp: "thực hiện" (đã làm chưa) và
// "kết quả" (đã có chưa). Nháp kết quả không hiện nội dung — chưa ai chịu
// trách nhiệm về chữ trong đó.
//
// BÁC SĨ ĐIỀN KẾT QUẢ NGAY ĐÂY (Tuyền 23/09/2026 tối: "không cần cái duyệt kết
// quả nữa, duyệt làm gì khi ta có thể tự điền vào đây"). [Điền kết quả] mở đúng
// phiếu kết quả của chỉ định (cùng engine, cùng [Hoàn tất] như phòng dịch vụ).
// Mẫu: mẫu đã gắn cho dịch vụ → mẫu gợi ý của phiếu v5 → 18 mẫu dự phòng.
// Mở [Xem kết quả] là "đã xem" (như nút ở Bàn khám) — máy chủ ghi, màn không tự
// quyết ai được tính.

import { useState } from "react";

import PhieuKetQua from "../PhieuKetQua";
import Button from "@/components/ui/Button";
import Chip, { type ChipTone } from "@/components/ui/Chip";
import {
  giaTriDoc,
  NHAN_KET_QUA,
  type ChiDinhVaKetQua,
  type KetQuaMotChiDinh,
  type MauKetQuaNgan,
} from "@/lib/phieu-kham";

const TONE: Record<ChiDinhVaKetQua["ket_qua_trang_thai"], ChipTone> = {
  CO_KET_QUA: "success",
  DANG_NHAP: "warning",
  CHUA_CO: "neutral",
};

function ghiDaXem(orderId: string) {
  // Chỉ để máy chủ ghi "đã xem" (bác sĩ / thư ký / BS siêu âm); nội dung đã có
  // sẵn ở đây. Hỏng thì thôi — không chặn việc đọc.
  void fetch(`/api/phieu?xem=${orderId}`, { cache: "no-store" }).catch(() => undefined);
}

export default function KetQuaChiDinh({
  ds,
  mauDuPhong = [],
  goiYMau = {},
  choDien = false,
  onDoi,
}: {
  ds: ChiDinhVaKetQua[];
  /** 18 mẫu kết quả đang bật — khi dịch vụ chưa gắn mẫu nào. */
  mauDuPhong?: MauKetQuaNgan[];
  /** service_code → mã mẫu gợi ý từ phiếu v5 (không kèm `KQ_`). */
  goiYMau?: Record<string, string>;
  /** Người đang mở có quyền điền kết quả (máy chủ vẫn kiểm lại). */
  choDien?: boolean;
  onDoi?: () => void;
}) {
  const [mo, setMo] = useState<string | null>(null);
  const [dien, setDien] = useState<string | null>(null);
  const mauCho = (d: ChiDinhVaKetQua): MauKetQuaNgan[] => {
    if (d.mau_ket_qua && d.mau_ket_qua.length > 0) return d.mau_ket_qua;
    const g = goiYMau[d.service_code];
    const goiY = g ? mauDuPhong.filter((m) => m.ma === g) : [];
    return goiY.length > 0 ? [...goiY, ...mauDuPhong.filter((m) => m.ma !== g)] : mauDuPhong;
  };
  if (ds.length === 0) {
    return <p className="text-body text-ink-faint">Chưa có chỉ định nào trong lượt này.</p>;
  }
  return (
    <ul className="divide-y divide-hairline rounded-card border border-hairline bg-surface">
      {ds.map((d) => {
        const dangMo = mo === d.service_order_id;
        return (
          <li key={d.service_order_id} className="px-3 py-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-body font-medium text-ink">{d.ten_hien_thi}</span>
              <Chip tone={TONE[d.ket_qua_trang_thai]}>
                {NHAN_KET_QUA[d.ket_qua_trang_thai]}
              </Chip>
              {d.ket_qua.some((k) => k.dang_sua) ? (
                <Chip tone="warning">Đang sửa lại — bản dưới vẫn chính thức</Chip>
              ) : null}
              <span className="ml-auto" />
              {d.ket_qua.length > 0 ? (
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  aria-expanded={dangMo}
                  onClick={() => {
                    if (!dangMo && d.ket_qua_trang_thai === "CO_KET_QUA") {
                      ghiDaXem(d.service_order_id);
                    }
                    setMo(dangMo ? null : d.service_order_id);
                  }}
                >
                  {dangMo ? "Thu gọn" : "Xem kết quả"}
                </Button>
              ) : null}
              {choDien ? (
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  aria-expanded={dien === d.service_order_id}
                  onClick={() =>
                    setDien(dien === d.service_order_id ? null : d.service_order_id)
                  }
                >
                  {dien === d.service_order_id ? "Đóng phiếu kết quả" : "Điền kết quả"}
                </Button>
              ) : null}
            </div>
            {dien === d.service_order_id ? (
              <div className="mt-2">
                <PhieuKetQua
                  serviceOrderId={d.service_order_id}
                  mau={mauCho(d)}
                  mauMacDinh={
                    d.ket_qua.find((k) => k.loai === "PHIEU")?.form_id?.replace(/^KQ_/, "") ??
                    (d.mau_ket_qua?.[0]?.ma || goiYMau[d.service_code] || null)
                  }
                  onHoanTat={() => onDoi?.()}
                />
              </div>
            ) : null}
            {dangMo ? (
              <div className="mt-2 space-y-3">
                {d.ket_qua.map((k) => (
                  <MotKetQua key={k.phieu_id ?? k.tep_id} k={k} />
                ))}
              </div>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

function MotKetQua({ k }: { k: KetQuaMotChiDinh }) {
  if (k.loai === "TEP") {
    return (
      <p className="text-body text-ink">
        Tệp {k.loai_tep}: {k.ten ?? "(không tên)"}
      </p>
    );
  }
  if (k.trang_thai !== "READY" || !k.khung || !k.du_lieu) {
    return <p className="text-body text-ink-muted">{k.ten}: đang nhập kết quả.</p>;
  }
  const duLieu = k.du_lieu;
  return (
    <div className="rounded-control bg-surface-muted p-3">
      <p className="text-meta font-semibold text-ink-muted">
        {k.ten}
        {k.ban_thu && k.ban_thu > 1 ? ` · bản ${k.ban_thu}` : ""}
      </p>
      <dl className="mt-1 space-y-1">
        {k.khung.flatMap((m) =>
          m.block.map((o) => (
            <div key={o.ma} className="flex flex-col gap-0.5 sm:flex-row sm:gap-2">
              <dt className="text-meta text-ink-muted sm:w-40 sm:shrink-0">{o.ten}</dt>
              <dd className="whitespace-pre-wrap text-body text-ink">
                {giaTriDoc(o, duLieu[o.ma])}
              </dd>
            </div>
          )),
        )}
      </dl>
    </div>
  );
}
