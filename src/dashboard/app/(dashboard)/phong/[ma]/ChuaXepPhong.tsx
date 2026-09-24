"use client";

// KHÁCH ĐÃ TRẢ TIỀN MÀ CHƯA XẾP PHÒNG — hiện ở MỌI phòng làm được dịch vụ ấy
// (Tuyền 24/09/2026: "kể cả lễ tân không chỉ định thì khách này vẫn có thể xuất
// hiện ở hàng đợi và có thể khám ở các dịch vụ khả thi"). Phòng nào rảnh bấm
// [Nhận vào phòng này] → lệnh xếp phòng thường (`xep-phong-v1`): máy chủ vẫn hỏi
// quyền, cổng tiền, revision, cơ sở. Hai phòng bấm cùng lúc → một bên nhận câu
// từ chối của máy chủ (revision đã đổi), danh sách tự nạp lại.
//
// Danh sách do máy chủ trả (`chua_xep_phong` của hàng chờ phòng) — màn không tự
// suy ai "đủ điều kiện".

import { useState } from "react";

import Button from "@/components/ui/Button";

import { guiThaoTac } from "../../_lam-viec/api";

export interface KhachChuaXep {
  id: string;
  visit_id: string;
  ten: string;
  khach: string | null;
  ma_khach: string | null;
  routing_revision: number;
}

export default function ChuaXepPhong({
  roomId,
  ds,
  onDaNhan,
}: {
  roomId: string;
  ds: KhachChuaXep[];
  onDaNhan: () => void;
}) {
  const [dang, setDang] = useState<string | null>(null);
  const [loi, setLoi] = useState<string | null>(null);

  if (ds.length === 0) return null;

  const nhan = async (k: KhachChuaXep) => {
    setDang(k.id);
    setLoi(null);
    const kq = await guiThaoTac("xep-phong-v1", k.id, {
      room_id: roomId,
      expected_routing_revision: k.routing_revision,
      reason_code: "INITIAL_ASSIGNMENT",
    });
    setDang(null);
    if (!kq.ok) setLoi(`${k.khach ?? "Khách"} · ${k.ten}: ${kq.loi}`);
    onDaNhan();
  };

  return (
    <section
      aria-label="Khách đã trả tiền chưa xếp phòng"
      className="space-y-2 rounded-card border border-warning bg-warning-bg p-3"
    >
      <p className="text-meta font-semibold uppercase tracking-wide text-warning">
        Đã trả tiền — chưa xếp phòng ({ds.length})
      </p>
      <ul className="space-y-2">
        {ds.map((k) => (
          <li key={k.id} className="flex flex-wrap items-center gap-2">
            <span className="min-w-0 flex-1 text-body text-ink">
              <span className="font-semibold">{k.khach ?? "—"}</span>
              {k.ma_khach ? <span className="text-ink-muted"> · {k.ma_khach}</span> : null}
              <span className="block text-meta text-ink-muted">{k.ten}</span>
            </span>
            <Button
              type="button"
              size="sm"
              variant="primary"
              disabled={dang !== null}
              onClick={() => void nhan(k)}
            >
              {dang === k.id ? "Đang nhận…" : "Nhận vào phòng này"}
            </Button>
          </li>
        ))}
      </ul>
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </section>
  );
}
