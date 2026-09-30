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

import { useEffect, useState } from "react";
import { nhanLoi } from "@/lib/loi-api";
import { laDicom } from "@/lib/phieu-kham";
import { useRouter } from "next/navigation";
import { FileImage, FileVideo, FileText, Check } from "lucide-react";

import Lightbox from "@/components/ui/Lightbox";

import { tepXem } from "../_lam-viec/AnhKetQua";
import { type CoXoaTep, DaXoaGanDay, NutXoaTep, type TepDaXoa } from "../_lam-viec/XoaTep";

export interface TepKetQuaRow {
  id: string;
  appointment_id: string | null;
  /** Tệp là kết quả của chỉ định nào (null = chưa gắn — tải từ màn Khách hàng). */
  service_order_id?: string | null;
  ten_hien_thi: string | null;
  loai_tep: string;
  mime: string;
  so_byte: number;
  tai_len_luc: string;
  tai_len_boi: string | null;
  gui_luc: string | null;
  gui_kenh: string | null;
  gui_boi: string | null;
  /** Bác sĩ cho phép gửi lúc nào (null = chưa) — CSKH chỉ gửi sau mốc này. */
  cho_phep_gui_luc: string | null;
  cho_phep_gui_boi: string | null;
  /** false = tệp siêu âm / thủ thuật — không tính vào "Có kết quả xét nghiệm". */
  la_ket_qua_xet_nghiem?: boolean;
  /** Trạng thái xác nhận tệp external: CHO_XAC_NHAN, HOP_LE, TU_CHOI, THU_HOI (null = internal) */
  xac_nhan_trang_thai?: string | null;
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

/** Tệp này CSKH gửi được chưa: tệp nội bộ luôn được; tệp đối tác phải đã
 *  xác nhận đúng người, đúng chỉ định (HOP_LE). Bác sĩ cho phép KHÔNG còn là
 *  điều kiện (23/09/2026). */
export function coTheGui(t: { xac_nhan_trang_thai?: string | null }): boolean {
  return t.xac_nhan_trang_thai == null || t.xac_nhan_trang_thai === "HOP_LE";
}

/** Một chỉ định của lượt — ô "Kết quả của chỉ định nào" (27/09/2026, đợt 3). */
interface ChiDinhCuaLuot {
  service_order_id: string;
  service_name: string | null;
  service_code: string;
  lan: number | null;
}

/** Chỉ định của lượt đang chọn, đọc từ máy chủ. null = chưa đọc / đọc hỏng
 *  (tải lên vẫn được, tệp vào mục "chưa gắn chỉ định"). */
function useChiDinhCuaLuot(appointmentId: string | null, bat: boolean) {
  // Nhớ kèm KHOÁ lượt: đổi lượt thì danh sách cũ tự thành "chưa đọc" — không
  // bao giờ cho chọn chỉ định của lượt khác.
  const [doc, setDoc] = useState<{ khoa: string; ds: ChiDinhCuaLuot[] | null } | null>(null);
  useEffect(() => {
    if (!bat || !appointmentId) return;
    let song = true;
    void fetch(`/api/cskh/ket-qua/chi-dinh?appointment_id=${encodeURIComponent(appointmentId)}`, {
      cache: "no-store",
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((d: { items?: ChiDinhCuaLuot[] } | null) => {
        if (song) setDoc({ khoa: appointmentId, ds: d?.items ?? null });
      })
      .catch(() => {
        if (song) setDoc({ khoa: appointmentId, ds: null });
      });
    return () => {
      song = false;
    };
  }, [appointmentId, bat]);
  return bat && appointmentId && doc?.khoa === appointmentId ? doc.ds : null;
}

export default function TepKetQua({
  clinicPatientId,
  appointmentId,
  items,
  readOnly = false,
  onDaThayDoi,
}: {
  clinicPatientId: string;
  appointmentId: string | null;
  /** Nạp server-side rồi truyền xuống — không nạp trong effect. */
  items: TepKetQuaRow[];
  /** Chỉ xem nội dung; không dựng control tải lên hoặc xác nhận đã gửi. */
  readOnly?: boolean;
  /** Nơi nạp danh sách PHÍA TRÌNH DUYỆT truyền hàm nạp lại vào đây.
   *
   *  `router.refresh()` chỉ dựng lại phần server. Khối nào nạp danh sách trong
   *  effect (TepCuaLuotKham — hồ sơ khám, phòng siêu âm) thì refresh KHÔNG chạy
   *  lại effect ấy, nên tệp vừa tải lên thành công mà không hiện ra — người dùng
   *  tưởng hỏng rồi tải lên lần nữa. */
  onDaThayDoi?: () => void;
}) {
  const router = useRouter();
  const [dangTai, setDangTai] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [xem, setXem] = useState<string | null>(null);
  const [dangGui, setDangGui] = useState<string | null>(null);
  // Hộp xem chung (lát 5, 26/09/2026): lật qua MỌI ảnh / video của khách.
  const [phongTo, setPhongTo] = useState<number | null>(null);
  // Tệp là kết quả của CHỈ ĐỊNH nào (27/09/2026, đợt 3 — "Doppler âm vật không
  // hiển thị ảnh"): tệp tải ở đây trước kia chỉ mang lịch hẹn, không vào dòng
  // chỉ định nào ở phiếu khám. Không bắt buộc: lượt chưa có chỉ định vẫn tải
  // được, tệp hiện ở mục "chưa gắn chỉ định". Máy chủ kiểm chỉ định thuộc lượt.
  const chiDinh = useChiDinhCuaLuot(appointmentId, !readOnly);
  const [chonTho, setChiDinhChon] = useState("");
  // Chỉ giữ lựa chọn còn nằm trong danh sách của lượt ĐANG chọn.
  const chiDinhChon = (chiDinh ?? []).some((c) => c.service_order_id === chonTho) ? chonTho : "";
  const tenChiDinh = new Map(
    (chiDinh ?? []).map((c) => [c.service_order_id, c.service_name ?? c.service_code]),
  );

  // XOÁ MỀM (V9, 30/09/2026): cờ `xoa_duoc` và danh sách đã xoá do MÁY CHỦ trả
  // ở danh sách tệp của khách — màn này không tự suy ai xoá được.
  const [coXoa, setCoXoa] = useState<Record<string, CoXoaTep>>({});
  const [daXoa, setDaXoa] = useState<TepDaXoa[]>([]);
  const [lanNapXoa, setLanNapXoa] = useState(0);
  const khoaItems = items.map((t) => t.id).join(",");
  useEffect(() => {
    if (readOnly) return;
    let song = true;
    void fetch(`/api/cskh/ket-qua?clinic_patient_id=${encodeURIComponent(clinicPatientId)}`, {
      cache: "no-store",
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((d: { items?: (CoXoaTep & { id: string })[]; da_xoa?: TepDaXoa[] } | null) => {
        if (!song || !d) return;
        setCoXoa(Object.fromEntries((d.items ?? []).map((t) => [t.id, t])));
        setDaXoa((d.da_xoa ?? []).filter((t) => t.appointment_id === appointmentId));
      })
      .catch(() => {});
    return () => {
      song = false;
    };
  }, [clinicPatientId, appointmentId, readOnly, lanNapXoa, khoaItems]);

  function daDoiTep() {
    setLanNapXoa((n) => n + 1);
    if (onDaThayDoi) onDaThayDoi();
    else router.refresh();
  }

  async function taiLen(files: FileList | null) {
    if (!appointmentId) {
      setLoi("Chọn một lượt khám trước khi tải kết quả.");
      return;
    }
    if (!files || files.length === 0) return;
    setDangTai(true);
    setLoi(null);
    for (const f of Array.from(files)) {
      const fd = new FormData();
      fd.append("clinic_patient_id", clinicPatientId);
      fd.append("appointment_id", appointmentId);
      if (chiDinhChon) fd.append("service_order_id", chiDinhChon);
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
    if (onDaThayDoi) onDaThayDoi();
    else router.refresh();
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
    if (onDaThayDoi) onDaThayDoi();
    else router.refresh();
  }

  const chuaGui = items.filter((t) => !t.gui_luc).length;
  // DICOM không vẽ được bằng thẻ img — không vào ô xem nhanh (đợt 3).
  const media = items.filter(
    (t) => (t.loai_tep === "ANH" && !laDicom(t.mime)) || t.loai_tep === "VIDEO",
  );

  return (
    <div className="border-t border-line px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-faint">
          Kết quả siêu âm / xét nghiệm
        </h3>
        {chuaGui > 0 && (
          <span className="rounded-chip bg-warning-bg px-2 py-0.5 text-label font-bold text-warning">
            {chuaGui} tệp chưa gửi
          </span>
        )}
      </div>

      {!readOnly && (
        <>
          {/* VIDEO ĐÃ MỞ (Tuyền 16/09/2026: "có chỗ up ảnh siêu âm, video siêu
              âm ngay trong giao diện để xem lại được"). Quang treo video ngày
              09/08 vì hai lý do, và cả hai đã có lời đáp: bản sao lưu hằng đêm
              nay chép cả thư mục tệp (backup-db.sh), và service từ chối ghi khi
              ổ đĩa xuống dưới ngưỡng an toàn. Backend vẫn giữ công tắc
              KET_QUA_VIDEO_UPLOAD_ENABLED — tắt nó là video bị từ chối kèm câu
              nói rõ lý do, không cần sửa giao diện. */}
          <label
            className={`mt-2 inline-flex items-center gap-1.5 rounded-control border border-dashed border-line px-3 py-1.5 text-label font-semibold text-ink-soft ${
              appointmentId
                ? "cursor-pointer hover:bg-surface-muted"
                : "cursor-not-allowed opacity-60"
            }`}
          >
            {dangTai ? "Đang tải lên…" : "+ Tải ảnh / video / phiếu"}
            <input
              type="file"
              multiple
              disabled={dangTai || !appointmentId}
              accept="image/*,.dcm,application/dicom,video/mp4,video/quicktime,video/webm,application/pdf,.docx,.xlsx"
              className="hidden"
              onChange={(e) => {
                void taiLen(e.target.files);
                // Chọn lại đúng tệp đó lần nữa vẫn phải kích hoạt onChange.
                e.target.value = "";
              }}
            />
          </label>

          {!appointmentId && (
            <p className="mt-1 text-label text-warning">
              Chọn một lượt khám để tải và gửi đúng kết quả của lượt đó.
            </p>
          )}

          {appointmentId && chiDinh && chiDinh.length > 0 ? (
            <label className="mt-2 block">
              <span className="text-label font-semibold text-ink-soft">
                Kết quả của chỉ định nào
              </span>
              <select
                value={chiDinhChon}
                onChange={(e) => setChiDinhChon(e.target.value)}
                disabled={dangTai}
                className="mt-1 w-full rounded-control border border-line bg-surface px-3 py-1.5 text-label text-ink"
              >
                <option value="">— Chưa gắn chỉ định —</option>
                {chiDinh.map((c) => (
                  <option key={c.service_order_id} value={c.service_order_id}>
                    {c.service_name ?? c.service_code}
                    {c.lan ? ` · lần ${c.lan}` : ""}
                  </option>
                ))}
              </select>
            </label>
          ) : null}

          <p className="mt-1 text-label leading-snug text-ink-faint">
            Nhận ảnh JPG/PNG, DICOM (chỉ tải về), video MP4/MOV/WebM, phiếu PDF.
          </p>
        </>
      )}

      {loi && <p className="mt-1.5 text-label text-danger">{loi}</p>}

      {/* XEM LẠI NGAY TRONG MÀN. Ảnh hiện thành ô xem nhanh; video hiện thành ô
          có biểu tượng — không tải trước nội dung video, chỉ khi bấm mở. Bấm vào
          là mở khung xem lớn ngay trên màn, không mở tab mới. */}
      {media.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {media.map((t, i) => {
              const url = `/api/cskh/ket-qua/${t.id}/noi-dung`;
              return (
                <button
                  key={`nhanh-${t.id}`}
                  type="button"
                  onClick={() => setPhongTo(i)}
                  title={t.ten_hien_thi ?? "Xem"}
                  className="relative size-24 overflow-hidden rounded-lg border border-line bg-surface-sunken"
                >
                  {t.loai_tep === "ANH" ? (
                    /* eslint-disable-next-line @next/next/no-img-element --
                       ảnh đi qua route XÁC THỰC, không qua bộ tối ưu ảnh dùng
                       chung (không mang cookie phiên → 401). */
                    <img
                      src={url}
                      alt={t.ten_hien_thi ?? "Ảnh"}
                      loading="lazy"
                      className="size-full object-cover"
                    />
                  ) : (
                    <span className="grid size-full place-items-center bg-ink text-white">
                      <FileVideo className="size-8" />
                    </span>
                  )}
                </button>
              );
            })}
        </div>
      )}

      {phongTo !== null && (
        <Lightbox
          tieuDe="Kết quả của khách"
          tep={media.map((t) =>
            tepXem({
              id: t.id,
              ten: t.ten_hien_thi,
              loai_tep: t.loai_tep,
              mime: t.mime,
              phu: gio(t.tai_len_luc),
            }),
          )}
          batDau={phongTo}
          veThaoTac={
            readOnly
              ? undefined
              : (x) =>
                  coXoa[x.id] ? (
                    <NutXoaTep
                      tepId={x.id}
                      ten={x.ten}
                      co={coXoa[x.id]}
                      nenToi
                      onDaXoa={() => {
                        setPhongTo(null);
                        daDoiTep();
                      }}
                    />
                  ) : null
          }
          onDong={() => setPhongTo(null)}
        />
      )}

      {!readOnly ? <DaXoaGanDay ds={daXoa} onXong={daDoiTep} /> : null}

      {items.length === 0 ? (
        <p className="mt-2 text-label text-ink-faint">
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
                <div className="flex items-center gap-2 text-label">
                  <Icon className="size-3.5 shrink-0 text-ink-faint" />
                  {readOnly ? (
                    <span className="min-w-0 flex-1 truncate text-left font-medium text-ink-soft">
                      {t.ten_hien_thi ?? "(không tên)"}
                    </span>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setXem(dangXem ? null : t.id)}
                      className="min-w-0 flex-1 truncate text-left font-medium text-brand-700 hover:underline"
                    >
                      {t.ten_hien_thi ?? "(không tên)"}
                    </button>
                  )}
                  <span className="shrink-0 font-mono text-ink-faint">
                    {coChu(t.so_byte)}
                  </span>
                </div>

                <p className="mt-0.5 text-label text-ink-muted">
                  {gio(t.tai_len_luc)}
                  {t.tai_len_boi && ` · ${t.tai_len_boi}`}
                  {t.service_order_id
                    ? tenChiDinh.has(t.service_order_id)
                      ? ` · ${tenChiDinh.get(t.service_order_id)}`
                      : ""
                    : " · chưa gắn chỉ định"}
                  {t.gui_luc && (
                    <span className="ml-1 inline-flex items-center gap-0.5 text-success">
                      <Check className="size-3" strokeWidth={3} />
                      đã gửi {gio(t.gui_luc)}
                      {t.gui_kenh && ` (${t.gui_kenh})`}
                    </span>
                  )}
                </p>

                {!readOnly && coXoa[t.id] ? (
                  <div className="mt-1 flex justify-end">
                    <NutXoaTep
                      tepId={t.id}
                      ten={t.ten_hien_thi}
                      co={coXoa[t.id]}
                      onDaXoa={daDoiTep}
                    />
                  </div>
                ) : null}

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
                    ) : t.loai_tep === "ANH" && !laDicom(t.mime) ? (
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
                        href={laDicom(t.mime) ? `${url}?tai=1` : url}
                        target={laDicom(t.mime) ? undefined : "_blank"}
                        rel="noreferrer"
                        className="text-label font-semibold text-brand-700 hover:underline"
                      >
                        {laDicom(t.mime)
                          ? "DICOM — Tải về (không xem trước được trên trình duyệt)"
                          : "Mở phiếu trong tab mới →"}
                      </a>
                    )}
                  </div>
                )}

                {!t.gui_luc && t.xac_nhan_trang_thai === "CHO_XAC_NHAN" && (
                  <p className="mt-1.5 inline-flex items-center gap-1 rounded-chip bg-warning-bg px-2 py-0.5 text-label font-bold text-warning">
                    Chờ xác nhận đúng người/chỉ định
                  </p>
                )}
                {!t.gui_luc && t.cho_phep_gui_luc && (
                  <p className="mt-1 text-label text-success">
                    {t.cho_phep_gui_boi ?? "Bác sĩ"} đã cho phép gửi {gio(t.cho_phep_gui_luc)}
                  </p>
                )}
                {/* GỬI ĐƯỢC NGAY (Tuyền chốt 23/09/2026): không còn đợi bác sĩ
                    cho phép. Tệp đối tác vẫn phải xác nhận đúng người/chỉ định. */}
                {!readOnly && !t.gui_luc && coTheGui(t) && (
                  <div className="mt-1.5 flex flex-wrap items-center gap-1">
                    {/* NHÃN NÓI ĐÚNG SỰ THẬT: người xác nhận đã gửi, hệ thống
                        chưa tự gửi được (send_zalo.py luôn delivered=False). */}
                    <span className="text-label text-ink-muted">
                      Xác nhận đã gửi qua:
                    </span>
                    {KENH.map(([ma, nhan]) => (
                      <button
                        key={ma}
                        type="button"
                        disabled={dangGui !== null}
                        onClick={() => void danhDauDaGui(t.id, ma)}
                        className="rounded-full px-2 py-0.5 text-label font-medium text-ink-soft ring-1 ring-inset ring-line hover:bg-surface disabled:opacity-50"
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
