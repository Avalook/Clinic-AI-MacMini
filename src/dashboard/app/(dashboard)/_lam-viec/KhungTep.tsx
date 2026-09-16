"use client";

// Ô TẢI VÀ Ô XEM LÀ MỘT (Tuyền 16/09/2026): *"bình thường ô đủ to nhưng có chữ
// gửi ảnh video vào đây, sau khi tải xong thì nó lưu … và có metadata ở
// database rồi biết của khách nào rồi, không mất được, và nó cho xem luôn trực
// tiếp ở ô đó"*.
//
// Mỗi tệp gắn vào MỘT CHỈ ĐỊNH (siêu âm, xét nghiệm, thủ thuật) — máy chủ kiểm
// chỉ định ấy đúng là của khách này rồi mới nhận, và đánh mốc "đã có kết quả,
// chờ bác sĩ duyệt". Tệp nằm ở kho lưu trữ cấu hình trên máy chủ (hiện là
// Viettel File Storage); ở đây chỉ có đường xem qua cửa đã xác thực.

import { useCallback, useEffect, useRef, useState } from "react";
import { FileText, UploadCloud, X } from "lucide-react";
import { nhanLoi } from "@/lib/loi-api";

interface Tep {
  id: string;
  ten_hien_thi: string | null;
  loai_tep: "ANH" | "VIDEO" | "PDF" | string;
  mime: string;
  so_byte: number;
  tai_len_luc: string;
  tai_len_boi: string | null;
  service_order_id: string | null;
}

function coChu(byte: number): string {
  if (byte < 1024 * 1024) return `${Math.max(1, Math.round(byte / 1024))} KB`;
  return `${(byte / 1024 / 1024).toFixed(1)} MB`;
}

function gio(iso: string): string {
  return new Date(iso).toLocaleString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  });
}

const duongXem = (id: string) => `/api/cskh/ket-qua/${id}/noi-dung`;

export default function KhungTep({
  clinicPatientId,
  serviceOrderId,
  choTaiLen = true,
  tieuDe = "Ảnh · video · phiếu kết quả",
  onDaTaiLen,
}: {
  clinicPatientId: string;
  serviceOrderId: string;
  /** false = chỉ xem (ví dụ bác sĩ đang duyệt). */
  choTaiLen?: boolean;
  tieuDe?: string;
  onDaTaiLen?: () => void;
}) {
  const [teps, setTeps] = useState<Tep[] | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [dangTai, setDangTai] = useState<string | null>(null);
  const [keoVao, setKeoVao] = useState(false);
  const [phongTo, setPhongTo] = useState<Tep | null>(null);
  const [lanNap, setLanNap] = useState(0);
  const oChon = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let huy = false;
    void fetch(
      `/api/cskh/ket-qua?clinic_patient_id=${encodeURIComponent(clinicPatientId)}`,
      { cache: "no-store" },
    )
      .then(async (r) => {
        const d = (await r.json().catch(() => null)) as
          | { items?: Tep[]; error?: string; message?: string }
          | null;
        if (huy) return;
        if (!r.ok) {
          setLoi(nhanLoi(d, "Không đọc được tệp kết quả."));
          return;
        }
        setTeps(
          (d?.items ?? [])
            .filter((t) => t.service_order_id === serviceOrderId)
            // Cũ trước: đọc theo thứ tự đã chụp.
            .sort((a, b) => a.tai_len_luc.localeCompare(b.tai_len_luc)),
        );
      })
      .catch(() => {
        if (!huy) setLoi("Mất kết nối tới máy chủ.");
      });
    return () => {
      huy = true;
    };
  }, [clinicPatientId, serviceOrderId, lanNap]);

  const taiLen = useCallback(
    async (files: FileList | File[] | null) => {
      const ds = Array.from(files ?? []);
      if (ds.length === 0) return;
      setLoi(null);
      for (const [i, f] of ds.entries()) {
        setDangTai(`Đang gửi ${i + 1}/${ds.length}: ${f.name}`);
        const fd = new FormData();
        fd.append("clinic_patient_id", clinicPatientId);
        fd.append("service_order_id", serviceOrderId);
        fd.append("file", f);
        try {
          const r = await fetch("/api/cskh/ket-qua", { method: "POST", body: fd });
          if (!r.ok) {
            const d = await r.json().catch(() => null);
            // Nói rõ TỆP NÀO hỏng — tệp trước nó đã lưu xong rồi.
            setLoi(`${f.name}: ${nhanLoi(d, "không gửi được.")}`);
            break;
          }
        } catch {
          setLoi(`${f.name}: mất kết nối — tệp này CHƯA được lưu.`);
          break;
        }
      }
      setDangTai(null);
      setLanNap((n) => n + 1);
      onDaTaiLen?.();
    },
    [clinicPatientId, serviceOrderId, onDaTaiLen],
  );

  const coTep = (teps?.length ?? 0) > 0;

  return (
    <section
      aria-label={tieuDe}
      onDragOver={(e) => {
        if (!choTaiLen) return;
        e.preventDefault();
        setKeoVao(true);
      }}
      onDragLeave={() => setKeoVao(false)}
      onDrop={(e) => {
        if (!choTaiLen) return;
        e.preventDefault();
        setKeoVao(false);
        void taiLen(e.dataTransfer.files);
      }}
      className={`rounded-card border-2 border-dashed p-3 transition-colors ${
        keoVao ? "border-brand-500 bg-brand-50" : "border-line bg-surface"
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-ink">{tieuDe}</h3>
        {coTep ? (
          <span className="text-label text-ink-muted">{teps!.length} tệp đã lưu</span>
        ) : null}
      </div>

      {choTaiLen ? (
        <>
          <input
            ref={oChon}
            type="file"
            multiple
            accept="image/*,video/mp4,video/quicktime,video/webm,application/pdf"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files ? Array.from(e.target.files) : [];
              // Xoá ngay: chọn lại đúng tệp ấy vẫn phải bắn sự kiện.
              e.target.value = "";
              void taiLen(f);
            }}
          />
          <button
            type="button"
            disabled={dangTai !== null}
            onClick={() => oChon.current?.click()}
            className={`mt-2 flex w-full flex-col items-center justify-center gap-1 rounded-control px-4 text-center text-ink-soft hover:bg-surface-muted disabled:opacity-60 ${
              coTep ? "min-h-16 py-3" : "min-h-40 py-8"
            }`}
          >
            <UploadCloud className={coTep ? "size-5" : "size-9"} aria-hidden />
            <span className="text-sm font-semibold text-ink">
              {dangTai ?? "Gửi ảnh, video, phiếu PDF vào đây"}
            </span>
            {dangTai === null ? (
              <span className="text-label text-ink-muted">
                Kéo thả tệp vào ô này hoặc bấm để chọn · ảnh JPG/PNG/DICOM, video
                MP4/MOV/WebM, PDF
              </span>
            ) : null}
          </button>
        </>
      ) : null}

      {loi ? (
        <p role="alert" className="mt-2 text-label text-danger">
          {loi}
        </p>
      ) : null}

      {teps === null && !loi ? (
        <p className="mt-2 text-label text-ink-muted">Đang tải tệp…</p>
      ) : null}
      {teps !== null && !coTep && !choTaiLen ? (
        <p className="mt-2 text-label text-ink-muted">Chưa có tệp nào.</p>
      ) : null}

      {/* XEM NGAY TRONG Ô. Ảnh hiện thẳng, video có nút phát, PDF mở trang đầu. */}
      {coTep ? (
        <ul className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {teps!.map((t) => (
            <li
              key={t.id}
              className="overflow-hidden rounded-control border border-line bg-surface-muted"
            >
              {t.loai_tep === "ANH" ? (
                <button
                  type="button"
                  onClick={() => setPhongTo(t)}
                  className="block w-full"
                  title="Bấm để xem lớn"
                >
                  {/* eslint-disable-next-line @next/next/no-img-element -- ảnh đi
                      qua cửa XÁC THỰC; bộ tối ưu ảnh chung không mang cookie phiên. */}
                  <img
                    src={duongXem(t.id)}
                    alt={t.ten_hien_thi ?? "Ảnh kết quả"}
                    loading="lazy"
                    className="aspect-video w-full bg-black object-contain"
                  />
                </button>
              ) : t.loai_tep === "VIDEO" ? (
                <video
                  src={duongXem(t.id)}
                  controls
                  preload="metadata"
                  className="aspect-video w-full bg-black"
                />
              ) : (
                <button
                  type="button"
                  onClick={() => setPhongTo(t)}
                  className="flex aspect-video w-full flex-col items-center justify-center gap-2 bg-surface text-ink-soft"
                >
                  <FileText className="size-10" aria-hidden />
                  <span className="text-label font-semibold">Mở phiếu PDF</span>
                </button>
              )}
              <p className="truncate px-2 py-1.5 text-label text-ink-muted">
                {t.ten_hien_thi ?? "(không tên)"} · {coChu(t.so_byte)} ·{" "}
                {gio(t.tai_len_luc)}
                {t.tai_len_boi ? ` · ${t.tai_len_boi}` : ""}
              </p>
            </li>
          ))}
        </ul>
      ) : null}

      {phongTo ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={phongTo.ten_hien_thi ?? "Xem tệp"}
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/80 p-4"
          onClick={() => setPhongTo(null)}
        >
          <div
            className="flex h-full max-h-[92vh] w-full max-w-5xl flex-col gap-2"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between gap-2 text-white">
              <p className="min-w-0 truncate text-sm font-semibold">
                {phongTo.ten_hien_thi ?? "(không tên)"}
              </p>
              <button
                type="button"
                onClick={() => setPhongTo(null)}
                className="inline-flex items-center gap-1 rounded-control bg-surface px-3 py-1 text-sm font-semibold text-ink"
              >
                <X className="size-4" aria-hidden /> Đóng
              </button>
            </div>
            {phongTo.loai_tep === "PDF" ? (
              <iframe
                src={duongXem(phongTo.id)}
                title={phongTo.ten_hien_thi ?? "Phiếu PDF"}
                className="min-h-0 w-full flex-1 rounded-control bg-surface"
              />
            ) : (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img
                src={duongXem(phongTo.id)}
                alt={phongTo.ten_hien_thi ?? "Ảnh"}
                className="min-h-0 w-full flex-1 rounded-control bg-black object-contain"
              />
            )}
          </div>
        </div>
      ) : null}
    </section>
  );
}
