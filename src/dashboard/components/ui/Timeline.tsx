/**
 * Dải mốc theo THỜI GIAN — "khách đã đi qua đâu, chờ bao lâu giữa hai chặng".
 *
 * Khác `Stepper`: Stepper trả lời "đang ở bước nào" của MỘT quy trình cố định;
 * Timeline trả lời "mất bao lâu" — nhãn nằm TRÊN ĐOẠN NỐI giữa hai mốc (khoảng
 * chờ, "đang 12 phút"), vì khoảng chờ mới là thứ người ở bàn khám hỏi (bản giao
 * diện mẫu Tuyền duyệt 26/09/2026).
 *
 * Màn hẹp: dải cuộn ngang, mỗi mốc giữ bề rộng tối thiểu — không bóp chữ.
 * Component chỉ VẼ; nhãn đoạn nối do nơi gọi tính (lib/hanh-trinh).
 */

import type { ReactNode } from "react";

export type TrangThaiMoc = "xong" | "dang" | "chua";

export interface MocTimeline {
  khoa: string;
  ten: string;
  /** Nơi / người: "Lễ tân", "Phòng siêu âm · Đối tác". */
  noi?: string;
  /** "08:02", "08:20 → 08:35", "Lần 1 09:40 · Lần 2 10:20". */
  gio?: string;
  trangThai: TrangThaiMoc;
}

export interface DoanTimeline {
  /** "15 phút", "chờ 8 phút", "hôm trước"; null = không ghi. */
  nhan: string | null;
  trangThai: TrangThaiMoc;
}

const CHAM: Record<TrangThaiMoc, string> = {
  xong: "border-status-completed bg-status-completed",
  dang: "border-brand-600 bg-surface ring-4 ring-brand-100",
  chua: "border-line-strong bg-surface",
};

const DOAN: Record<TrangThaiMoc, string> = {
  xong: "bg-status-completed",
  dang: "bg-brand-600",
  chua: "bg-line",
};

const NHAN_DOAN: Record<TrangThaiMoc, string> = {
  xong: "text-ink-muted",
  dang: "font-semibold text-brand-700",
  chua: "text-ink-faint",
};

const TEN: Record<TrangThaiMoc, string> = {
  xong: "text-ink",
  dang: "font-semibold text-ink",
  chua: "text-ink-faint",
};

export default function Timeline({
  moc,
  doan,
  dau,
  nhanAria = "Hành trình",
}: {
  moc: MocTimeline[];
  /** Đoạn nối SAU mốc thứ i (độ dài = moc.length - 1). */
  doan: DoanTimeline[];
  /** Dòng trên dải — thường là "Đang ở …". */
  dau?: ReactNode;
  nhanAria?: string;
}) {
  return (
    <div className="space-y-2">
      {dau}
      <ol aria-label={nhanAria} className="flex overflow-x-auto pb-1">
        {moc.map((m, i) => {
          const d = doan[i];
          return (
            <li key={m.khoa} className="flex min-w-28 flex-1 flex-col last:min-w-20 last:flex-none">
              {/* mt-4: chỗ cho nhãn đoạn nối nằm TRÊN đường, tràn được ra hai
                  bên thay vì bị cắt khi đoạn nối hẹp. */}
              <div className="mt-4 flex h-7 items-center">
                <span
                  aria-hidden
                  className={`size-3.5 shrink-0 rounded-full border-2 ${CHAM[m.trangThai]}`}
                />
                {i < moc.length - 1 ? (
                  <span className="relative mx-1 flex h-7 flex-1 items-center">
                    <span
                      aria-hidden
                      className={`h-0.5 w-full ${DOAN[d?.trangThai ?? "chua"]}`}
                    />
                    {d?.nhan ? (
                      <span
                        className={`absolute bottom-full left-1/2 -translate-x-1/2 whitespace-nowrap text-meta ${NHAN_DOAN[d.trangThai]}`}
                      >
                        {d.nhan}
                      </span>
                    ) : null}
                  </span>
                ) : null}
              </div>
              <div className="pr-3">
                <p className={`text-body ${TEN[m.trangThai]}`}>{m.ten}</p>
                {m.noi ? <p className="text-meta text-ink-muted">{m.noi}</p> : null}
                <p className="text-meta tabular-nums text-ink-soft">{m.gio || "—"}</p>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
