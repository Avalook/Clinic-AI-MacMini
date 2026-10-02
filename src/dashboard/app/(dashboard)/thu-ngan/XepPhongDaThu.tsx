"use client";

// XẾP / ĐỔI PHÒNG SAU KHI THU (Tuyền 24/09/2026): "thanh toán xong vẫn chỉ định
// [phòng] được bình thường". Trước đây ô "Làm ở phòng" chỉ có TRƯỚC khi thu —
// thu xong chỉ định rời khỏi ô chọn dịch vụ, lễ tân mất chỗ chọn phòng.
//
// Danh sách = chỉ định khách đã chốt làm, chưa bắt đầu — V10 (30/09/2026, làm
// trước, thu sau): đã trả hay chưa đều có (máy chủ trả trong
// `xep_phong` của bảng thu ngân). Chọn phòng dùng lại ĐÚNG khối `DoiPhong` của
// Bàn khám / Xem lượt: phòng làm được + số người chờ, lệnh xếp phòng thường.
//
// P3 (Tuyền 25/09/2026): quầy thu đổi phòng LÚC NÀO CŨNG ĐƯỢC (nguồn `quay_thu`).
// 29/09/2026: kể cả khi trưởng ca đã xếp (bỏ khoá) — mọi lần đổi hiện ở lịch sử
// Hành trình khách.

import NutInPhieu from "@/components/ui/NutInPhieu";

import DoiPhong from "../_lam-viec/DoiPhong";

export interface DaTraChoPhong {
  id: string;
  ten: string;
  room_id: string | null;
  phong: string | null;
  routing_revision: number;
  /** Bác sĩ đã chọn trong phòng nhiều bác sĩ ("BS X", máy chủ viết). */
  bac_si_lam?: string | null;
}

export default function XepPhongDaThu({
  ds,
  onDoi,
  visitId,
}: {
  ds: DaTraChoPhong[];
  onDoi: () => void;
  /** Có thì hiện nút in PHIẾU HƯỚNG DẪN phòng — in được cả khi chưa thu
   *  (làm trước, thu sau — Tuyền 30/09/2026). */
  visitId?: string;
}) {
  if (ds.length === 0) return null;
  return (
    <div className="space-y-2 border-b border-line px-4 py-3 last:border-b-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-meta font-semibold uppercase tracking-wide text-ink-muted">
          Phòng làm dịch vụ (khách đã chốt)
        </p>
        {visitId ? (
          <NutInPhieu href={`/print/phieu-thu/${visitId}?loai=huong_dan`} size="md">
            In phiếu hướng dẫn phòng
          </NutInPhieu>
        ) : null}
      </div>
      <ul className="space-y-2">
        {ds.map((c) => (
          <li key={c.id}>
            <p className="text-body text-ink">
              {c.ten}
              <span className={c.phong ? "text-ink-muted" : "text-warning"}>
                {" "}
                · {c.phong ?? "vui lòng chọn phòng"}
                {c.phong && c.bac_si_lam ? ` · ${c.bac_si_lam}` : ""}
              </span>
            </p>
            <DoiPhong
              orderId={c.id}
              phongHienTaiId={c.room_id}
              routingRevision={c.routing_revision}
              choDoi
              onDaDoi={onDoi}
              nguon="quay_thu"
            />
          </li>
        ))}
      </ul>
    </div>
  );
}
