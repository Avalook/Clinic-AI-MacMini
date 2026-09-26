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

import { useCallback, useEffect, useMemo, useState } from "react";
import { FileText } from "lucide-react";

import Dropzone from "@/components/ui/Dropzone";
import Lightbox, { type TepXem } from "@/components/ui/Lightbox";
import { doCoTep, guiTepCoTienDo } from "@/lib/gui-tep-co-tien-do";
import { nhanLoi, type ThanLoi } from "@/lib/loi-api";

import AnhKetQua, { duongXemTep, tepXem } from "./AnhKetQua";

interface Tep {
  id: string;
  ten_hien_thi: string | null;
  loai_tep: "ANH" | "VIDEO" | "PDF" | string;
  mime: string;
  so_byte: number;
  tai_len_luc: string;
  tai_len_boi: string | null;
  service_order_id: string | null;
  /** Bên trong mẫu hai bên (Thai A=0, Thai B=1…); null = tệp chung / tệp cũ. */
  ben?: number | null;
}

const coChu = doCoTep;

function gio(iso: string): string {
  return new Date(iso).toLocaleString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  });
}

const duongXem = duongXemTep;

const MIME_DOCX =
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

/** XEM WORD NGAY TRONG MÀN: đổi DOCX → HTML ngay trên trình duyệt (mammoth),
 *  hiện trong khung CÁCH LY (`sandbox` rỗng: không chạy mã, không đi đâu). Không
 *  thêm dịch vụ chuyển đổi nào trên máy chủ. Excel chưa xem trực tiếp được — mở
 *  bằng máy. */
function XemTaiLieu({ tep }: { tep: Tep }) {
  const [html, setHtml] = useState<string | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const laWord = tep.mime === MIME_DOCX;
  useEffect(() => {
    if (!laWord) return;
    let huy = false;
    void (async () => {
      try {
        const r = await fetch(duongXem(tep.id), { cache: "no-store" });
        if (!r.ok) throw new Error(String(r.status));
        const buf = await r.arrayBuffer();
        const mammoth = await import("mammoth/mammoth.browser");
        const ra = await mammoth.convertToHtml({ arrayBuffer: buf });
        if (!huy) setHtml(ra.value || "<p>(Tài liệu trống)</p>");
      } catch {
        if (!huy) setLoi("Không đọc được tài liệu Word này — mở bằng máy để xem.");
      }
    })();
    return () => {
      huy = true;
    };
  }, [laWord, tep.id]);

  if (!laWord) {
    return (
      <div className="flex aspect-video w-full flex-col items-center justify-center gap-2 bg-surface p-3 text-center text-ink-soft">
        <FileText className="size-10" aria-hidden />
        <span className="text-label">Bảng tính Excel chưa xem trực tiếp được.</span>
        <a
          href={duongXem(tep.id)}
          className="text-label font-semibold text-brand-700 underline"
        >
          Mở bằng máy
        </a>
      </div>
    );
  }
  if (loi) {
    return <p className="p-3 text-label text-danger">{loi}</p>;
  }
  if (html === null) {
    return <p className="p-3 text-label text-ink-muted">Đang mở tài liệu…</p>;
  }
  return (
    <iframe
      title={tep.ten_hien_thi ?? "Tài liệu"}
      sandbox=""
      srcDoc={`<meta charset="utf-8"><style>body{font:14px/1.5 system-ui,sans-serif;margin:12px}img{max-width:100%}table{border-collapse:collapse}td,th{border:1px solid silver;padding:4px}</style>${html}`}
      className="h-72 w-full bg-surface"
    />
  );
}

export default function KhungTep({
  clinicPatientId,
  serviceOrderId,
  choTaiLen = true,
  tieuDe = "Ảnh · video · phiếu kết quả",
  onDaTaiLen,
  ben,
}: {
  clinicPatientId: string;
  serviceOrderId: string;
  /** false = chỉ xem (ví dụ bác sĩ đang duyệt). */
  choTaiLen?: boolean;
  tieuDe?: string;
  onDaTaiLen?: () => void;
  /** Mẫu hai bên (26/09/2026): ô tải của MỘT bên — tệp gửi lên gắn `ben`, danh
   *  sách chỉ hiện tệp của bên ấy (tệp cũ chưa gắn bên xếp vào bên đầu). */
  ben?: { so: number; ten: string };
}) {
  const [teps, setTeps] = useState<Tep[] | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [dangTai, setDangTai] = useState<string | null>(null);
  const [mo, setMo] = useState<{ i: number; luoi: boolean } | null>(null);
  const [lanNap, setLanNap] = useState(0);
  // Số nguyên, không phải object: cha tạo object `ben` mới mỗi lần vẽ.
  const benSo = ben?.so;

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
            .filter(
              (t) =>
                benSo === undefined ||
                t.ben === benSo ||
                (benSo === 0 && (t.ben === null || t.ben === undefined)),
            )
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
  }, [clinicPatientId, serviceOrderId, lanNap, benSo]);

  const taiLen = useCallback(
    async (files: FileList | File[] | null) => {
      const ds = Array.from(files ?? []);
      if (ds.length === 0) return;
      setLoi(null);
      // Tệp lỗi KHÔNG chặn các tệp sau (smoke 18/09): trước đây một video bị
      // từ chối làm dừng cả loạt, PDF/Word chọn cùng lúc không bao giờ được gửi
      // và người dùng không biết. Gom lỗi từng tệp, báo một lần ở cuối.
      const loiTung: string[] = [];
      for (const [i, f] of ds.entries()) {
        const nhan = `Đang gửi ${i + 1}/${ds.length}: ${f.name} (${doCoTep(f.size)})`;
        setDangTai(nhan);
        const fd = new FormData();
        fd.append("clinic_patient_id", clinicPatientId);
        fd.append("service_order_id", serviceOrderId);
        if (benSo !== undefined) fd.append("ben", String(benSo));
        fd.append("file", f);
        try {
          const r = await guiTepCoTienDo("/api/cskh/ket-qua", fd, (pt) =>
            setDangTai(
              pt >= 100
                ? `Đang cất vào kho ${i + 1}/${ds.length}: ${f.name} — đừng đóng trang`
                : `${nhan} — ${pt}%`,
            ),
          );
          if (!r.ok) {
            // Nói rõ TỆP NÀO hỏng — các tệp khác vẫn gửi tiếp.
            loiTung.push(`${f.name}: ${nhanLoi(r.data as ThanLoi | null, "không gửi được.")}`);
          }
        } catch {
          loiTung.push(`${f.name}: mất kết nối — tệp này CHƯA được lưu.`);
        }
      }
      setLoi(loiTung.length > 0 ? loiTung.join(" · ") : null);
      setDangTai(null);
      setLanNap((n) => n + 1);
      onDaTaiLen?.();
    },
    [clinicPatientId, serviceOrderId, onDaTaiLen, benSo],
  );

  /** Tải về từng tệp một (không nén) — trình duyệt hỏi một lần cho nhiều tệp. */
  const taiTatCa = useCallback(() => {
    for (const t of teps ?? []) {
      const a = document.createElement("a");
      a.href = `${duongXem(t.id)}?tai=1`;
      a.rel = "noopener";
      document.body.appendChild(a);
      a.click();
      a.remove();
    }
  }, [teps]);

  const coTep = (teps?.length ?? 0) > 0;
  const xem: TepXem[] = useMemo(
    () =>
      (teps ?? []).map((t) =>
        tepXem({
          id: t.id,
          ten: t.ten_hien_thi,
          loai_tep: t.loai_tep === "TAI_LIEU" ? "TAI_LIEU" : t.loai_tep,
          phu: [coChu(t.so_byte), gio(t.tai_len_luc), t.tai_len_boi].filter(Boolean).join(" · "),
        }),
      ),
    [teps],
  );

  return (
    <section aria-label={tieuDe} className="rounded-card border border-line bg-surface p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-ink">{ben ? ben.ten : tieuDe}</h3>
        {coTep ? (
          <span className="flex items-center gap-2 text-label text-ink-muted">
            {teps!.length} tệp đã lưu
            {teps!.length > 1 ? (
              <button
                type="button"
                onClick={taiTatCa}
                className="font-semibold text-brand-700 underline underline-offset-4"
              >
                Tải tất cả
              </button>
            ) : null}
          </span>
        ) : null}
      </div>

      {choTaiLen ? (
        <div className="mt-2">
          <Dropzone
            onChon={(ds) => void taiLen(ds)}
            disabled={dangTai !== null}
            gon={coTep}
            accept="image/*,video/mp4,video/quicktime,video/webm,application/pdf,.docx,.xlsx"
            nhan={dangTai ?? "Gửi ảnh, video, PDF, Word vào đây"}
            phu={
              dangTai === null
                ? "Kéo thả tệp vào ô này hoặc bấm để chọn · ảnh JPG/PNG/WEBP/GIF/DICOM, video MP4/MOV/WebM, PDF, Word (.docx), Excel (.xlsx)"
                : undefined
            }
          />
        </div>
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

      {/* XEM NGAY TRONG Ô (lát 5): ≤3 tệp hiện từng tấm lớn, nhiều hơn xếp
          chồng theo loại; bấm mở hộp xem lật được qua MỌI tệp của chỉ định. */}
      {coTep ? (
        <div className="mt-3">
          <AnhKetQua tep={xem} lon onMo={(i, luoi) => setMo({ i, luoi: Boolean(luoi) })} />
        </div>
      ) : null}

      {mo ? (
        <Lightbox
          tieuDe={ben ? ben.ten : tieuDe}
          tep={xem}
          batDau={mo.i}
          luoiBanDau={mo.luoi}
          veTaiLieu={(t) => {
            const goc = teps?.find((x) => x.id === t.id);
            return goc ? <XemTaiLieu tep={goc} /> : null;
          }}
          onDong={() => setMo(null)}
        />
      ) : null}
    </section>
  );
}
