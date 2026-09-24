"use client";

// XẾP / ĐỔI PHÒNG SAU KHI THU (Tuyền 24/09/2026): "thanh toán xong vẫn chỉ định
// [phòng] được bình thường". Trước đây ô "Làm ở phòng" chỉ có TRƯỚC khi thu —
// thu xong chỉ định rời khỏi ô chọn dịch vụ, lễ tân mất chỗ chọn phòng.
//
// Danh sách = chỉ định đã trả, khách làm, chưa bắt đầu (máy chủ trả trong
// `xep_phong` của bảng thu ngân). Chọn phòng dùng lại ĐÚNG khối `DoiPhong` của
// Bàn khám / Xem lượt: phòng làm được + số người chờ, lệnh xếp phòng thường.

import DoiPhong from "../_lam-viec/DoiPhong";

export interface DaTraChoPhong {
  id: string;
  ten: string;
  room_id: string | null;
  phong: string | null;
  routing_revision: number;
}

export default function XepPhongDaThu({
  ds,
  onDoi,
}: {
  ds: DaTraChoPhong[];
  onDoi: () => void;
}) {
  if (ds.length === 0) return null;
  return (
    <div className="space-y-2 border-b border-line px-4 py-3 last:border-b-0">
      <p className="text-meta font-semibold uppercase tracking-wide text-ink-muted">
        Phòng làm dịch vụ (đã thu)
      </p>
      <ul className="space-y-2">
        {ds.map((c) => (
          <li key={c.id}>
            <p className="text-body text-ink">
              {c.ten}
              <span className={c.phong ? "text-ink-muted" : "text-warning"}>
                {" "}
                · {c.phong ?? "chưa xếp phòng"}
              </span>
            </p>
            <DoiPhong
              orderId={c.id}
              phongHienTaiId={c.room_id}
              routingRevision={c.routing_revision}
              choDoi
              onDaDoi={onDoi}
            />
          </li>
        ))}
      </ul>
    </div>
  );
}
