"use client";

// ẢNH · VIDEO · TÀI LIỆU của MỘT chỉ định, dạng xem nhanh (lát 5, 26/09/2026).
//
// Bản giao diện mẫu Tuyền duyệt: ≤3 tệp thì hiện từng tấm; nhiều hơn thì mỗi
// loại (ảnh / video / tài liệu) xếp thành một "chồng giấy", kèm "Xem tất cả N →"
// mở lưới. Bấm tấm nào mở hộp xem (Lightbox) ĐÚNG tấm ấy — nơi gọi giữ hộp.
//
// Dùng ở: khung tệp phòng dịch vụ (`KhungTep`, tấm lớn) và dòng chỉ định trong
// phiếu khám (`KetQuaChiDinh`, tấm nhỏ). Chỉ hiển thị — mở tệp KHÔNG ghi "đã xem"
// (việc ấy là lệnh riêng của nút Xem kết quả).

import { FileText } from "lucide-react";

import type { TepXem } from "@/components/ui/Lightbox";

export const duongXemTep = (id: string) => `/api/cskh/ket-qua/${id}/noi-dung`;

/** Tệp máy chủ (tep_ket_qua) → mục xem của Lightbox. */
export function tepXem(t: {
  id: string;
  ten: string | null;
  loai_tep: string;
  phu?: string;
}): TepXem {
  return {
    id: t.id,
    src: duongXemTep(t.id),
    ten: t.ten ?? "(không tên)",
    loai: t.loai_tep,
    phu: t.phu,
    taiVe: `${duongXemTep(t.id)}?tai=1`,
  };
}

const NHOM: { loai: (l: string) => boolean; nhan: string }[] = [
  { loai: (l) => l === "ANH", nhan: "ảnh" },
  { loai: (l) => l === "VIDEO", nhan: "video" },
  { loai: (l) => l !== "ANH" && l !== "VIDEO", nhan: "tài liệu" },
];

function Mat({ t, gon = false }: { t: TepXem; gon?: boolean }) {
  if (t.loai === "ANH") {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- ảnh đi qua cửa XÁC THỰC; bộ tối ưu ảnh không mang cookie phiên.
      <img src={t.src} alt={t.ten} loading="lazy" className="h-full w-full bg-ink object-cover" />
    );
  }
  if (t.loai === "VIDEO") {
    return (
      <span className="relative block h-full w-full bg-ink">
        <video src={`${t.src}#t=0.8`} preload="metadata" muted playsInline className="h-full w-full object-cover" />
        <span aria-hidden className="absolute inset-0 flex items-center justify-center text-title text-white">
          ▶
        </span>
      </span>
    );
  }
  return (
    <span className="flex h-full w-full flex-col items-center justify-center gap-1 bg-surface-muted p-2 text-ink-soft">
      <FileText className="size-6" aria-hidden />
      {/* Trong chồng giấy, nhãn "n tài liệu" nằm dưới — tên sẽ bị đè. */}
      {gon ? null : <span className="line-clamp-2 text-center text-label">{t.ten}</span>}
    </span>
  );
}

export default function AnhKetQua({
  tep,
  onMo,
  lon = false,
}: {
  tep: TepXem[];
  /** Mở hộp xem ở tấm thứ `i`; `luoi` = mở dạng lưới. */
  onMo: (i: number, luoi?: boolean) => void;
  lon?: boolean;
}) {
  if (tep.length === 0) return null;
  const co = lon ? "aspect-video w-full" : "size-20";

  if (tep.length <= 3) {
    return (
      <ul className={lon ? "grid grid-cols-1 gap-3 sm:grid-cols-2" : "flex flex-wrap gap-2"}>
        {tep.map((t, i) => (
          <li key={t.id}>
            <button
              type="button"
              onClick={() => onMo(i)}
              title="Bấm để xem lớn"
              className={`block overflow-hidden rounded-control border border-line ${co}`}
            >
              <Mat t={t} />
            </button>
          </li>
        ))}
      </ul>
    );
  }

  const chong = NHOM.map((g) => ({
    nhan: g.nhan,
    ds: tep.map((t, i) => [t, i] as const).filter(([t]) => g.loai(t.loai)),
  })).filter((g) => g.ds.length > 0);

  return (
    <div className="flex flex-wrap items-end gap-4">
      {chong.map((g) => (
        <button
          key={g.nhan}
          type="button"
          onClick={() => onMo(g.ds[0][1])}
          title={`Xem ${g.ds.length} ${g.nhan}`}
          className={`relative ${lon ? "h-28 w-40" : "h-20 w-24"}`}
        >
          {g.ds
            .slice(0, 3)
            .reverse()
            .map(([t], k, arr) => {
              const lech = arr.length - 1 - k;
              return (
                <span
                  key={t.id}
                  className={`absolute inset-0 overflow-hidden rounded-control border border-line bg-surface ${
                    lech === 2 ? "translate-x-2 -translate-y-2" : lech === 1 ? "translate-x-1 -translate-y-1" : ""
                  }`}
                >
                  <Mat t={t} gon />
                </span>
              );
            })}
          <span className="absolute bottom-1 left-1 rounded-control bg-ink/80 px-1.5 text-label font-semibold text-white">
            {g.ds.length} {g.nhan}
          </span>
        </button>
      ))}
      <button
        type="button"
        onClick={() => onMo(0, true)}
        className="text-meta font-semibold text-brand-700 underline underline-offset-4"
      >
        Xem tất cả {tep.length} →
      </button>
    </div>
  );
}
