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

import { Download, FileText } from "lucide-react";

import type { TepXem } from "@/components/ui/Lightbox";
import { laDicom } from "@/lib/phieu-kham";

export const duongXemTep = (id: string) => `/api/cskh/ket-qua/${id}/noi-dung`;

/** Loại xem của DICOM (27/09/2026, đợt 3): trình duyệt không vẽ được — ô "Tải
 *  về", không phải ảnh. Máy chủ lưu DICOM mới là TAI_LIEU; dòng cũ lỡ mang ANH
 *  nhận ra bằng mime. */
export const LOAI_DICOM = "DICOM";

/** Tệp máy chủ (tep_ket_qua) → mục xem của Lightbox. */
export function tepXem(t: {
  id: string;
  ten: string | null;
  loai_tep: string;
  mime?: string | null;
  phu?: string;
}): TepXem {
  return {
    id: t.id,
    src: duongXemTep(t.id),
    ten: t.ten ?? "(không tên)",
    loai: laDicom(t.mime) ? LOAI_DICOM : t.loai_tep,
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
  if (t.loai === LOAI_DICOM) {
    return (
      <span className="flex h-full w-full flex-col items-center justify-center gap-1 bg-surface-muted p-2 text-ink-soft">
        <Download className="size-6" aria-hidden />
        <span className="text-label font-semibold">DICOM — Tải về</span>
        {gon ? null : <span className="line-clamp-1 text-center text-label">{t.ten}</span>}
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

/** "6 ảnh · 2 video · 1 tài liệu" — đầu khối ảnh của bản mẫu. */
export function demTep(tep: TepXem[]): string {
  return NHOM.map((g) => {
    const n = tep.filter((t) => g.loai(t.loai)).length;
    return n ? `${n} ${g.nhan}` : "";
  })
    .filter(Boolean)
    .join(" · ");
}

export default function AnhKetQua({
  tep,
  onMo,
  lon = false,
  dau = false,
}: {
  tep: TepXem[];
  /** Mở hộp xem ở tấm thứ `i`; `luoi` = mở dạng lưới. */
  onMo: (i: number, luoi?: boolean) => void;
  lon?: boolean;
  /** Đầu khối "ẢNH · VIDEO" + đếm (bản mẫu `mediaKhoi` ở phiếu khám). */
  dau?: boolean;
}) {
  if (tep.length === 0) return null;

  const dauKhoi = dau ? (
    <div className="flex items-baseline justify-between gap-2">
      <span className="text-label font-semibold uppercase tracking-wide text-ink-muted">Ảnh · video</span>
      <span className="text-meta text-ink-muted">{demTep(tep)}</span>
    </div>
  ) : null;

  if (tep.length <= 3) {
    return (
      <div className="space-y-2">
        {dauKhoi}
        <ul className={lon ? "grid grid-cols-1 gap-3 sm:grid-cols-2" : "grid grid-cols-3 gap-2 sm:grid-cols-4"}>
          {tep.map((t, i) => (
            <li key={t.id}>
              {t.loai === LOAI_DICOM && t.taiVe ? (
                // DICOM: không có gì để "xem lớn" — ô là đường TẢI VỀ luôn.
                <a
                  href={t.taiVe}
                  rel="noopener"
                  title={`Tải về ${t.ten}`}
                  className={`block w-full overflow-hidden rounded-control ring-1 ring-inset ring-hairline hover:bg-surface-sunken ${
                    lon ? "aspect-video" : "aspect-4/3"
                  }`}
                >
                  <Mat t={t} />
                </a>
              ) : (
                <button
                  type="button"
                  onClick={() => onMo(i)}
                  title="Bấm để xem lớn"
                  className={`group block w-full cursor-zoom-in overflow-hidden rounded-control bg-ink ring-1 ring-inset ring-hairline ${
                    lon ? "aspect-video" : "aspect-4/3"
                  }`}
                >
                  <span className="block h-full w-full transition-transform duration-100 group-hover:scale-105">
                    <Mat t={t} />
                  </span>
                </button>
              )}
            </li>
          ))}
        </ul>
      </div>
    );
  }

  // Nhiều tệp: mỗi loại một "chồng giấy" — ba tờ, hai tờ dưới xoay lệch, rê chuột
  // thì xoè ra (bản mẫu `.md-chong`).
  const chong = NHOM.map((g) => ({
    nhan: g.nhan,
    ds: tep.map((t, i) => [t, i] as const).filter(([t]) => g.loai(t.loai)),
  })).filter((g) => g.ds.length > 0);
  const XOAY = [
    "",
    "-rotate-6 -translate-x-1.5 translate-y-0.5 group-hover:-rotate-12 group-hover:-translate-x-3",
    "rotate-6 translate-x-2 translate-y-0.5 group-hover:rotate-12 group-hover:translate-x-3.5",
  ];

  return (
    <div className="space-y-2">
      {dauKhoi}
      <div className="flex flex-wrap gap-6 px-2 pt-2 pb-1">
        {chong.map((g) => (
          <button
            key={g.nhan}
            type="button"
            onClick={() => onMo(g.ds[0][1])}
            title={`Xem ${g.ds.length} ${g.nhan}`}
            className={`group relative ${lon ? "h-28 w-36" : "h-24 w-28"}`}
          >
            {g.ds
              .slice(0, 3)
              .reverse()
              .map(([t], k, arr) => (
                <span
                  key={t.id}
                  className={`absolute inset-x-0 top-0 bottom-3 overflow-hidden rounded-control border-2 border-surface bg-ink transition-transform duration-200 ${
                    XOAY[arr.length - 1 - k] ?? ""
                  }`}
                >
                  <Mat t={t} gon />
                </span>
              ))}
            <span className="absolute -bottom-1 left-1/2 grid h-5 -translate-x-1/2 place-items-center whitespace-nowrap rounded-chip bg-ink px-2 text-label font-semibold text-white">
              {g.ds.length} {g.nhan}
            </span>
          </button>
        ))}
      </div>
      <div className="text-center">
        <button
          type="button"
          onClick={() => onMo(0, true)}
          className="rounded-control px-3 py-1 text-meta font-semibold text-ink-muted hover:bg-surface-sunken"
        >
          Xem tất cả {tep.length} →
        </button>
      </div>
    </div>
  );
}
