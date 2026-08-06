"use client";

// Nút GỌI — nửa còn thiếu của màn cảnh báo.
//
// Màn này đã nói được "SA1 đang tắc, 4 người chờ, lâu nhất 38 phút". Nó không
// nói được VỚI AI. Trưởng ca nhìn thấy rồi phải rời màn hình, cầm điện thoại
// hoặc đi bộ sang.
//
// VAI ĐƯỢC GỌI KHAI TƯỜNG MINH, KHÔNG SUY TỪ PHÒNG. Đánh thức nhầm bộ phận
// đúng lúc đang tắc thì tệ hơn là bắt trưởng ca chọn một lần — và một phép suy
// từ mã phòng sang vai sẽ sai lặng lẽ vào ngày phòng khám đổi cách đặt tên.
//
// Bấm lại khi bên kia CHƯA xử lý thì KHÔNG tạo thêm thông báo; backend trả
// `da_goi_tu_truoc` và ở đây nói thẳng điều đó ra. Nếu không, trưởng ca bấm ba
// lần rồi tưởng mình vừa gọi ba lần.

import { useState } from "react";
import { PhoneCall } from "lucide-react";

const VAI = [
  { ma: "NURSE_ULTRASOUND", nhan: "Điều dưỡng" },
  { ma: "ULTRASOUND_DOCTOR", nhan: "BS Siêu âm" },
  { ma: "DOCTOR", nhan: "Bác sĩ" },
  { ma: "RECEPTION", nhan: "Lễ tân" },
  { ma: "CASHIER", nhan: "Thu ngân" },
  { ma: "PHARMACIST", nhan: "Dược sĩ" },
  { ma: "TKYK", nhan: "Thư ký y khoa" },
  { ma: "CSKH", nhan: "CSKH" },
] as const;

export default function NutGoiBoPhan({
  tieuDe,
  noiDung,
  nguonId,
  khan,
}: {
  tieuDe: string;
  noiDung: string;
  /** Khoá chống gọi trùng — thường là mã phòng. */
  nguonId: string | null;
  khan: boolean;
}) {
  const [vai, setVai] = useState<string>(VAI[0].ma);
  const [dangGui, setDangGui] = useState(false);
  const [ketQua, setKetQua] = useState<string | null>(null);

  async function goi() {
    setDangGui(true);
    setKetQua(null);
    try {
      const res = await fetch("/api/dispatch/alerts-call", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          vai_nhan: vai,
          tieu_de: tieuDe,
          noi_dung: noiDung,
          nguon_id: nguonId,
          muc_do: khan ? "KHAN" : "THUONG",
          duong_dan: "/truong-ca/canh-bao",
        }),
      });
      const d = (await res.json().catch(() => null)) as {
        error?: string;
        message?: string;
        da_goi_tu_truoc?: boolean;
      } | null;
      if (!res.ok) {
        setKetQua(d?.message ?? d?.error ?? "Không gọi được. Thử lại giúp em.");
        return;
      }
      setKetQua(
        d?.da_goi_tu_truoc
          ? "Đã gọi từ trước và bên kia chưa xử lý — không gửi thêm."
          : "Đã gửi thông báo.",
      );
    } finally {
      setDangGui(false);
    }
  }

  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center", marginTop: 8, marginLeft: 22 }}>
      <select
        value={vai}
        onChange={(e) => setVai(e.target.value)}
        aria-label="Gọi bộ phận nào"
        className="rounded-control border border-line bg-surface px-2 py-1 text-xs text-ink"
      >
        {VAI.map((v) => (
          <option key={v.ma} value={v.ma}>
            {v.nhan}
          </option>
        ))}
      </select>
      <button
        type="button"
        onClick={goi}
        disabled={dangGui}
        className="inline-flex items-center gap-1.5 rounded-control bg-brand-600 px-2.5 py-1 text-xs font-medium text-surface hover:bg-brand-700 disabled:opacity-50"
      >
        <PhoneCall size={12} />
        {dangGui ? "Đang gọi…" : "Gọi"}
      </button>
      {ketQua && (
        <span style={{ fontSize: 11, color: "var(--ink-muted)" }}>{ketQua}</span>
      )}
    </div>
  );
}
