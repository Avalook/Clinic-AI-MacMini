"use client";

// Mục C — KẾT QUẢ CẬN LÂM SÀNG theo từng chỉ định của lượt.
//
// Gắn bằng `service_order_id` (máy chủ đã nối). Hai chỉ định cùng tên là hai
// dòng riêng, kết quả không bao giờ chạy sang nhau. Tên dịch vụ chỉ để đọc.
//
// Hai lớp trạng thái đứng cạnh nhau, không gộp: "thực hiện" (đã làm chưa) và
// "kết quả" (đã có chưa). Nháp kết quả không hiện nội dung — chưa ai chịu
// trách nhiệm về chữ trong đó.

import { useState } from "react";

import Button from "@/components/ui/Button";
import Chip, { type ChipTone } from "@/components/ui/Chip";
import {
  giaTriDoc,
  NHAN_KET_QUA,
  type ChiDinhVaKetQua,
  type KetQuaMotChiDinh,
} from "@/lib/phieu-kham";

const TONE: Record<ChiDinhVaKetQua["ket_qua_trang_thai"], ChipTone> = {
  CO_KET_QUA: "success",
  DANG_NHAP: "warning",
  CHUA_CO: "neutral",
};

export default function KetQuaChiDinh({ ds }: { ds: ChiDinhVaKetQua[] }) {
  const [mo, setMo] = useState<string | null>(null);
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
                  onClick={() => setMo(dangMo ? null : d.service_order_id)}
                >
                  {dangMo ? "Thu gọn" : "Xem kết quả"}
                </Button>
              ) : null}
            </div>
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
