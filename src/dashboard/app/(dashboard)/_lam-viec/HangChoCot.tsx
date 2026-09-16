"use client";

// CỘT HÀNG CHỜ của một phòng — dùng chung cho bàn khám, phòng siêu âm, phòng
// thủ thuật, lấy mẫu. Thứ tự do MÁY CHỦ xếp (đang trong phòng → đang chờ → chờ
// khách xong việc khác → đã xong; trong mỗi nhóm: ưu tiên, rồi giờ vào hàng).
// Cột này chỉ chia nhóm để đọc, không tự xếp lại.

import { Star } from "lucide-react";
import { type DongHangCho, gioVn, soPhutTu } from "./api";

const NHOM: { ten: string; co: (d: DongHangCho) => boolean }[] = [
  { ten: "Đang trong phòng", co: (d) => d.trang_thai === "serving" },
  {
    ten: "Đang chờ",
    co: (d) => d.trang_thai === "waiting" || d.trang_thai === "called",
  },
  // Khách đang ở một bước khác (đang khám bác sĩ, đang siêu âm phòng khác):
  // vẫn là người của phòng này, chưa gọi vào được.
  { ten: "Đang làm việc khác", co: (d) => d.trang_thai === "blocked" },
  { ten: "Đã xong hôm nay", co: (d) => d.trang_thai === "done" },
];

export default function HangChoCot({
  dong,
  chon,
  onChon,
  trong = "Chưa có khách nào trong hàng chờ.",
}: {
  dong: DongHangCho[];
  chon: string | null;
  onChon: (id: string) => void;
  trong?: string;
}) {
  if (dong.length === 0) {
    return (
      <p className="rounded-card border border-line bg-surface p-4 text-sm text-ink-muted">
        {trong}
      </p>
    );
  }
  return (
    <div className="space-y-3">
      {NHOM.map((n) => {
        const ds = dong.filter(n.co);
        if (ds.length === 0) return null;
        return (
          <section key={n.ten}>
            <h3 className="mb-1 px-1 text-label font-semibold uppercase tracking-wide text-ink-muted">
              {n.ten} ({ds.length})
            </h3>
            <ul className="space-y-1">
              {ds.map((d) => {
                const dangChon = d.id === chon;
                const phut =
                  d.trang_thai === "serving"
                    ? soPhutTu(d.bat_dau_luc)
                    : d.trang_thai === "done"
                      ? ""
                      : soPhutTu(d.vao_hang_luc);
                return (
                  <li key={d.id}>
                    <button
                      type="button"
                      onClick={() => onChon(d.id)}
                      aria-pressed={dangChon}
                      className={`flex w-full items-start gap-2 rounded-control border px-2.5 py-2 text-left transition-colors ${
                        dangChon
                          ? "border-brand-500 bg-brand-50"
                          : "border-line bg-surface hover:bg-surface-muted"
                      } ${d.trang_thai === "done" ? "opacity-70" : ""}`}
                    >
                      <span className="grid size-8 shrink-0 place-items-center rounded-full bg-surface-sunken text-sm font-bold text-ink">
                        {d.so_thu_tu}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="flex items-center gap-1">
                          {d.uu_tien ? (
                            <Star
                              className="size-3.5 shrink-0 fill-warning text-warning"
                              aria-label="Ưu tiên"
                            />
                          ) : null}
                          <span
                            className={`truncate text-sm font-semibold ${
                              d.uu_tien ? "text-danger" : "text-ink"
                            }`}
                          >
                            {d.ten}
                          </span>
                        </span>
                        <span className="block truncate text-label text-ink-muted">
                          {d.viec ?? d.dich_vu_kham ?? "—"}
                          {d.loai === "KHAM" && d.bac_si ? ` · ${d.bac_si}` : ""}
                        </span>
                      </span>
                      <span className="shrink-0 text-right text-label text-ink-muted">
                        {d.trang_thai === "done" ? gioVn(d.xong_luc) : phut}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
