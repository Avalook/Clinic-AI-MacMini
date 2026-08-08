"use client";

// Khu tải kết quả siêu âm / xét nghiệm — BẢN MẪU, chưa lưu thật.
//
// Quang (08/08/2026): *"up video chỉ cần tạo giả thôi chưa cần thật"*. Nên đây
// là hình dáng của luồng, không phải luồng.
//
// VÌ SAO CHƯA LƯU THẬT, VÀ VÌ SAO PHẢI NÓI RA. Đo trên VPS hôm nay: không script
// sao lưu nào chạm tới thư mục tệp — `backup-db.sh` và `day-sao-luu-len-viettel
// .sh` chỉ `pg_dump`. Bật lưu thật trước khi vá sao lưu nghĩa là ảnh siêu âm của
// bệnh nhân nằm ngoài mọi bản sao lưu, và không ai biết cho tới hôm cần khôi
// phục.
//
// Một bản mẫu IM LẶNG thì tệ hơn không có: CSKH chọn tệp, thấy nó hiện lên,
// đóng trang, và tin rằng kết quả đã gửi cho khách. Nên mỗi tệp ở đây mang một
// nhãn nói thẳng là chưa lưu, và nút gửi bị khoá.

import { useState } from "react";
import { FileImage, FileVideo, FileText, X } from "lucide-react";

interface TepMau {
  ten: string;
  co: number;
  loai: "ANH" | "VIDEO" | "KHAC";
}

function doLoai(f: File): TepMau["loai"] {
  if (f.type.startsWith("image/")) return "ANH";
  if (f.type.startsWith("video/")) return "VIDEO";
  return "KHAC";
}

function coChu(byte: number): string {
  if (byte < 1024 * 1024) return `${Math.round(byte / 1024)} KB`;
  return `${(byte / 1024 / 1024).toFixed(1)} MB`;
}

const BIEU_TUONG = {
  ANH: FileImage,
  VIDEO: FileVideo,
  KHAC: FileText,
} as const;

export default function TepKetQuaMau() {
  const [tep, setTep] = useState<TepMau[]>([]);

  return (
    <div className="border-t border-line px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-faint">
          Kết quả siêu âm / xét nghiệm
        </h3>
        <span className="rounded-full bg-warning-bg px-2 py-0.5 text-[10px] font-bold text-warning">
          BẢN MẪU — CHƯA LƯU
        </span>
      </div>

      <p className="mt-1 text-[11px] text-ink-muted">
        Chọn tệp để xem luồng sẽ trông thế nào. Tệp{" "}
        <strong>không được gửi đi và không được lưu lại</strong> — rời trang là
        mất. Sao lưu hằng đêm chưa bao gồm tệp, nên chỗ này chỉ bật thật sau khi
        vá xong sao lưu.
      </p>

      <label className="mt-2 inline-flex cursor-pointer items-center gap-1.5 rounded-xl border border-dashed border-line px-3 py-1.5 text-[11px] font-semibold text-ink-soft hover:bg-surface-muted">
        + Chọn ảnh / video / phiếu
        <input
          type="file"
          multiple
          accept="image/*,video/*,application/pdf"
          className="hidden"
          onChange={(e) => {
            const ds = Array.from(e.target.files ?? []).map((f) => ({
              ten: f.name,
              co: f.size,
              loai: doLoai(f),
            }));
            setTep((cu) => [...cu, ...ds]);
            // Xoá giá trị để chọn lại đúng tệp đó lần nữa vẫn kích hoạt onChange.
            e.target.value = "";
          }}
        />
      </label>

      {tep.length > 0 && (
        <ul className="mt-2 space-y-1">
          {tep.map((t, i) => {
            const Icon = BIEU_TUONG[t.loai];
            return (
              <li
                key={`${t.ten}-${i}`}
                className="flex items-center gap-2 rounded-lg bg-surface-muted px-2 py-1 text-[11px] text-ink-soft"
              >
                <Icon className="size-3.5 shrink-0 text-ink-faint" />
                <span className="min-w-0 flex-1 truncate">{t.ten}</span>
                <span className="shrink-0 font-mono text-ink-faint">
                  {coChu(t.co)}
                </span>
                <button
                  type="button"
                  aria-label={`Bỏ ${t.ten}`}
                  onClick={() => setTep((cu) => cu.filter((_, k) => k !== i))}
                  className="shrink-0 rounded p-0.5 text-ink-faint hover:bg-danger-bg hover:text-danger"
                >
                  <X className="size-3" />
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {/* KHOÁ, KHÔNG PHẢI ẨN. Ẩn thì người dùng không biết bước này tồn tại;
          khoá kèm lý do thì họ biết nó sẽ có và vì sao chưa có. */}
      <button
        type="button"
        disabled
        title="Chưa nối — tệp chưa được lưu ở đâu cả"
        className="mt-2 w-full cursor-not-allowed rounded-xl border border-line bg-surface-muted py-1.5 text-[11px] font-semibold text-ink-muted opacity-70"
      >
        Gửi kết quả cho khách (chưa nối)
      </button>
    </div>
  );
}
