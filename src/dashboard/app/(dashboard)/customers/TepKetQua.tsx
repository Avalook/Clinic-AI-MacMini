"use client";

// Kết quả siêu âm / xét nghiệm — tải lên THẬT, xem được, và đánh dấu đã gửi.
//
// Thay cho bản mẫu ngày 08/08. Bản mẫu đúng ở một điểm và chỉ một: nó NÓI RA
// rằng nó chưa lưu gì. Giờ nó lưu thật, nên hai thứ phải thật theo:
//
//   · Sao lưu hằng đêm đã ôm tệp (20260809 / backup-db.sh). Bật tải lên trước
//     khi vá sao lưu là để ảnh bệnh nhân sống trên đúng một cái ổ đĩa.
//   · "Gửi" vẫn là NGƯỜI xác nhận đã gửi, không phải hệ thống tự gửi —
//     send_zalo.py luôn trả delivered=False. Nhãn nút nói đúng như vậy.

import { useState } from "react";
import { nhanLoi } from "@/lib/loi-api";
import { useRouter } from "next/navigation";
import { FileImage, FileVideo, FileText, Check } from "lucide-react";

export interface TepKetQuaRow {
  id: string;
  ten_hien_thi: string | null;
  loai_tep: string;
  mime: string;
  so_byte: number;
  tai_len_luc: string;
  tai_len_boi: string | null;
  gui_luc: string | null;
  gui_kenh: string | null;
  gui_boi: string | null;
}

const BIEU_TUONG = {
  ANH: FileImage,
  VIDEO: FileVideo,
  PDF: FileText,
} as const;

const KENH: [string, string][] = [
  ["ZALO", "Zalo"],
  ["SMS", "SMS"],
  ["TRUC_TIEP", "Đưa trực tiếp"],
  ["EMAIL", "Email"],
];

function coChu(byte: number): string {
  if (byte < 1024 * 1024) return `${Math.round(byte / 1024)} KB`;
  return `${(byte / 1024 / 1024).toFixed(1)} MB`;
}

function gio(iso: string): string {
  return new Date(iso).toLocaleString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  });
}

export default function TepKetQua({
  clinicPatientId,
  appointmentId,
  items,
}: {
  clinicPatientId: string;
  appointmentId: string | null;
  /** Nạp server-side rồi truyền xuống — không nạp trong effect. */
  items: TepKetQuaRow[];
}) {
  const router = useRouter();
  const [dangTai, setDangTai] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [xem, setXem] = useState<string | null>(null);
  const [dangGui, setDangGui] = useState<string | null>(null);

  async function taiLen(files: FileList | null) {
    if (!files || files.length === 0) return;
    setDangTai(true);
    setLoi(null);
    for (const f of Array.from(files)) {
      const fd = new FormData();
      fd.append("clinic_patient_id", clinicPatientId);
      if (appointmentId) fd.append("appointment_id", appointmentId);
      fd.append("file", f);
      const res = await fetch("/api/cskh/ket-qua", { method: "POST", body: fd });
      if (!res.ok) {
        const d = (await res.json().catch(() => null)) as
          | { error?: string; message?: string }
          | null;
        // Nói rõ TỆP NÀO hỏng: tải năm tệp mà chỉ báo "không tải được" thì
        // người dùng phải thử lại từng cái để biết cái nào.
        setLoi(`${f.name}: ${nhanLoi(d, "không tải lên được.")}`);
        setDangTai(false);
        return;
      }
    }
    setDangTai(false);
    router.refresh();
  }

  async function danhDauDaGui(id: string, kenh: string) {
    setDangGui(id);
    setLoi(null);
    const res = await fetch("/api/cskh/ket-qua", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, kenh }),
    });
    setDangGui(null);
    if (!res.ok) {
      const d = (await res.json().catch(() => null)) as
        | { error?: string; message?: string }
        | null;
      setLoi(nhanLoi(d, "Không đánh dấu được."));
      return;
    }
    router.refresh();
  }

  const chuaGui = items.filter((t) => !t.gui_luc).length;

  return (
    <div className="border-t border-line px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-faint">
          Kết quả siêu âm / xét nghiệm
        </h3>
        {chuaGui > 0 && (
          <span className="rounded-full bg-warning-bg px-2 py-0.5 text-[10px] font-bold text-warning">
            {chuaGui} tệp chưa gửi
          </span>
        )}
      </div>

      {/* VIDEO TREO LẠI — chưa nhận tải lên (Quang chốt 09/08/2026).
          Ổ đĩa VPS còn 30GB trên tổng 48GB. Một video siêu âm thực tế 15–25MB,
          trần cho phép tới 80MB; ba mươi khách một ngày là ~1GB/ngày, tức đầy
          đĩa trong khoảng năm tuần. Đầy đĩa ở đây KHÔNG chỉ mất ảnh — Postgres
          chạy cùng ổ ấy và sẽ dừng theo.
          Ảnh và phiếu PDF vẫn nhận bình thường (12MB / 20MB). Video đã tải lên
          từ trước VẪN xem và phát được — chỉ chặn tải MỚI, không xoá gì. */}
      <label className="mt-2 inline-flex cursor-pointer items-center gap-1.5 rounded-xl border border-dashed border-line px-3 py-1.5 text-[11px] font-semibold text-ink-soft hover:bg-surface-muted">
        {dangTai ? "Đang tải lên…" : "+ Tải ảnh / phiếu"}
        <input
          type="file"
          multiple
          disabled={dangTai}
          accept="image/*,application/pdf"
          className="hidden"
          onChange={(e) => {
            void taiLen(e.target.files);
            // Xoá giá trị để chọn lại đúng tệp đó lần nữa vẫn kích hoạt onChange.
            e.target.value = "";
          }}
        />
      </label>

      <p className="mt-1 text-[11px] leading-snug text-ink-faint">
        Video siêu âm: <b>đang xây dựng</b> — chưa tải lên được. Đang chờ chốt
        chỗ lưu riêng cho video để không ăn hết ổ đĩa của máy chủ.
      </p>

      {loi && <p className="mt-1.5 text-[11px] text-danger">{loi}</p>}

      {items.length === 0 ? (
        <p className="mt-2 text-[11px] text-ink-faint">
          Chưa có kết quả nào được tải lên.
        </p>
      ) : (
        <ul className="mt-2 space-y-1.5">
          {items.map((t) => {
            const Icon =
              BIEU_TUONG[t.loai_tep as keyof typeof BIEU_TUONG] ?? FileText;
            const url = `/api/cskh/ket-qua/${t.id}/noi-dung`;
            const dangXem = xem === t.id;
            return (
              <li
                key={t.id}
                className="rounded-lg border border-line bg-surface-muted p-2"
              >
                <div className="flex items-center gap-2 text-[11px]">
                  <Icon className="size-3.5 shrink-0 text-ink-faint" />
                  <button
                    type="button"
                    onClick={() => setXem(dangXem ? null : t.id)}
                    className="min-w-0 flex-1 truncate text-left font-medium text-brand-700 hover:underline"
                  >
                    {t.ten_hien_thi ?? "(không tên)"}
                  </button>
                  <span className="shrink-0 font-mono text-ink-faint">
                    {coChu(t.so_byte)}
                  </span>
                </div>

                <p className="mt-0.5 text-[11px] text-ink-muted">
                  {gio(t.tai_len_luc)}
                  {t.tai_len_boi && ` · ${t.tai_len_boi}`}
                  {t.gui_luc && (
                    <span className="ml-1 inline-flex items-center gap-0.5 text-success">
                      <Check className="size-3" strokeWidth={3} />
                      đã gửi {gio(t.gui_luc)}
                      {t.gui_kenh && ` (${t.gui_kenh})`}
                    </span>
                  )}
                </p>

                {dangXem && (
                  <div className="mt-1.5">
                    {t.loai_tep === "VIDEO" ? (
                      // `controls` + Range ở server = tua được. Không preload
                      // để mở panel không kéo về vài chục MB của mọi tệp.
                      <video
                        src={url}
                        controls
                        preload="none"
                        className="max-h-64 w-full rounded-lg bg-black"
                      />
                    ) : t.loai_tep === "ANH" ? (
                      /* eslint-disable-next-line @next/next/no-img-element --
                         ảnh đi qua route XÁC THỰC của chính mình, không phải
                         nguồn tĩnh: next/image sẽ đi lấy nó bằng tiến trình
                         tối ưu hoá — không mang cookie phiên — nên nhận 401 và
                         hiện ô vỡ. Đây là ảnh bệnh nhân, không phải ảnh trang
                         chủ; nó KHÔNG được đi qua bộ đệm dùng chung. */
                      <img
                        src={url}
                        alt={t.ten_hien_thi ?? "Kết quả"}
                        className="max-h-64 w-full rounded-lg object-contain"
                      />
                    ) : (
                      <a
                        href={url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[11px] font-semibold text-brand-700 hover:underline"
                      >
                        Mở phiếu trong tab mới →
                      </a>
                    )}
                  </div>
                )}

                {!t.gui_luc && (
                  <div className="mt-1.5 flex flex-wrap items-center gap-1">
                    {/* NHÃN NÓI ĐÚNG SỰ THẬT: người xác nhận đã gửi, hệ thống
                        chưa tự gửi được (send_zalo.py luôn delivered=False). */}
                    <span className="text-[11px] text-ink-muted">
                      Xác nhận đã gửi qua:
                    </span>
                    {KENH.map(([ma, nhan]) => (
                      <button
                        key={ma}
                        type="button"
                        disabled={dangGui !== null}
                        onClick={() => void danhDauDaGui(t.id, ma)}
                        className="rounded-full border border-line px-2 py-0.5 text-[11px] font-medium text-ink-soft hover:bg-surface disabled:opacity-50"
                      >
                        {nhan}
                      </button>
                    ))}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
