"use client";

/**
 * Hàng chờ xác nhận kết quả tệp từ đối tác (External Result Verification Queue).
 *
 * Chỉ dành cho người có capability 'ket_qua.xac_nhan'.
 * Chức năng: Kiểm tra tính hợp lệ về mặt vận hành (đúng bệnh nhân, đúng chỉ định,
 * tệp rõ ràng, không lỗi định dạng) trước khi chuyển qua Bác sĩ đánh giá chuyên môn
 * và cho phép gửi khách.
 *
 * CURRENT LIMITATION: SINGLE-PARTNER PILOT ONLY.
 */

import { useCallback, useEffect, useState } from "react";
import {
  Check,
  X,
  FileText,
  FileImage,
  FileVideo,
  AlertCircle,
  RefreshCw,
  ExternalLink,
  ShieldAlert,
  CheckCircle2,
} from "lucide-react";

export interface TepChoXacNhanRow {
  tep_id: string;
  clinic_patient_id: string;
  ten_khach: string;
  patient_code: string;
  service_order_id: string;
  ten_dich_vu: string;
  tai_len_luc: string;
  tai_len_boi_ten: string | null;
  tai_len_boi_vai: string | null;
  tai_len_boi_staff_id: string | null;
  ten_hien_thi: string | null;
  loai_tep: string;
  mime: string;
  xac_nhan_trang_thai: string;
  co_the_xac_nhan: boolean;
  khong_the_xac_nhan_ly_do: string | null;
}

const BIEU_TUONG = {
  ANH: FileImage,
  VIDEO: FileVideo,
  PDF: FileText,
} as const;

function gioVn(iso: string): string {
  try {
    return new Date(iso).toLocaleString("vi-VN", {
      timeZone: "Asia/Ho_Chi_Minh",
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export default function HangChoXacNhanKetQua() {
  const [items, setItems] = useState<TepChoXacNhanRow[] | null>(null);
  const [dangTai, setDangTai] = useState(true);
  const [loiChung, setLoiChung] = useState<string | null>(null);
  const [loiTheoDong, setLoiTheoDong] = useState<Record<string, string>>({});
  const [dangXuLy, setDangXuLy] = useState<string | null>(null);
  const [thongBaoThanhCong, setThongBaoThanhCong] = useState<string | null>(null);

  // Modal / form từ chối
  const [tuChoiId, setTuChoiId] = useState<string | null>(null);
  const [lyDoTuChoi, setLyDoTuChoi] = useState("");
  const [loiLyDo, setLoiLyDo] = useState<string | null>(null);

  const [lanNap, setLanNap] = useState(0);

  useEffect(() => {
    let huy = false;
    fetch("/api/cskh/ket-qua/cho-xac-nhan", { cache: "no-store" })
      .then(async (res) => {
        if (huy) return;
        if (res.status === 403) {
          setLoiChung(
            "Bạn không có quyền xác nhận kết quả. Vui lòng liên hệ Quản lý (Management) để được phân quyền.",
          );
          setItems([]);
          return;
        }
        if (!res.ok) {
          const body = (await res.json().catch(() => null)) as {
            error?: string;
            message?: string;
          } | null;
          setLoiChung(
            body?.error ?? body?.message ?? `Lỗi tải danh sách (HTTP ${res.status})`,
          );
          setItems([]);
          return;
        }
        const data = (await res.json()) as { items?: TepChoXacNhanRow[] };
        if (!huy) {
          setLoiChung(null);
          setItems(data.items ?? []);
        }
      })
      .catch(() => {
        if (!huy) {
          setLoiChung("Mất kết nối tới máy chủ. Vui lòng kiểm tra lại mạng.");
          setItems([]);
        }
      })
      .finally(() => {
        if (!huy) setDangTai(false);
      });

    return () => {
      huy = true;
    };
  }, [lanNap]);

  const taiDanhSach = useCallback(() => {
    setDangTai(true);
    setLanNap((n) => n + 1);
  }, []);

  // Tự ẩn thông báo thành công sau 5 giây
  useEffect(() => {
    if (!thongBaoThanhCong) return;
    const t = setTimeout(() => setThongBaoThanhCong(null), 5000);
    return () => clearTimeout(t);
  }, [thongBaoThanhCong]);

  async function xacNhan(id: string, trangThai: "HOP_LE" | "TU_CHOI", lyDo?: string) {
    if (dangXuLy) return;
    setDangXuLy(id);
    setLoiTheoDong((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });

    try {
      const payload: { trang_thai: string; ly_do?: string } = {
        trang_thai: trangThai,
      };
      if (trangThai === "TU_CHOI") {
        payload.ly_do = (lyDo ?? "").trim();
      }

      const res = await fetch(`/api/cskh/ket-qua/${id}/xac-nhan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const body = (await res.json().catch(() => null)) as {
        ok?: boolean;
        error?: string;
        message?: string;
      } | null;

      if (!res.ok) {
        const msg =
          body?.message ?? body?.error ?? `Không thực hiện được (HTTP ${res.status})`;
        setLoiTheoDong((prev) => ({ ...prev, [id]: msg }));
        return;
      }

      // Xóa dòng khỏi queue sau khi xử lý thành công
      setItems((prev) => (prev ? prev.filter((item) => item.tep_id !== id) : []));

      if (trangThai === "HOP_LE") {
        setThongBaoThanhCong("Đã xác nhận tệp đúng người/đúng chỉ định.");
      } else {
        setThongBaoThanhCong("Đã từ chối tệp kết quả.");
        setTuChoiId(null);
        setLyDoTuChoi("");
        setLoiLyDo(null);
      }
    } catch {
      setLoiTheoDong((prev) => ({
        ...prev,
        [id]: "Mất kết nối tới máy chủ khi gửi xác nhận.",
      }));
    } finally {
      setDangXuLy(null);
    }
  }

  function moHopThoaiTuChoi(id: string) {
    setTuChoiId(id);
    setLyDoTuChoi("");
    setLoiLyDo(null);
  }

  function xacNhanTuChoiSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!tuChoiId) return;
    const lyDo = lyDoTuChoi.trim();
    if (!lyDo) {
      setLoiLyDo("Vui lòng nhập lý do từ chối tệp.");
      return;
    }
    void xacNhan(tuChoiId, "TU_CHOI", lyDo);
  }

  return (
    <section className="space-y-4">
      {/* Thanh tiêu đề + tải lại */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-line bg-surface p-4 shadow-card">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h1 className="text-lg font-bold text-ink">
              Hàng chờ xác nhận kết quả đối tác
            </h1>
            {items !== null && (
              <span className="rounded-chip bg-warning-bg px-2.5 py-0.5 text-xs font-bold text-warning">
                {items.length} tệp
              </span>
            )}
          </div>
          <p className="mt-1 text-sm text-ink-muted">
            Kiểm tra tệp external đúng khách, đúng chỉ định trước khi chuyển Bác sĩ
            xem và cho phép gửi. (Pilot: Single-partner only)
          </p>
        </div>

        <button
          type="button"
          disabled={dangTai}
          onClick={() => void taiDanhSach()}
          className="inline-flex items-center gap-1.5 rounded-control border border-line bg-surface px-3 py-1.5 text-sm font-semibold text-ink-soft hover:bg-surface-muted disabled:opacity-50"
        >
          <RefreshCw className={`size-4 ${dangTai ? "animate-spin" : ""}`} />
          Tải lại
        </button>
      </div>

      {/* Thông báo toàn cục thành công */}
      {thongBaoThanhCong && (
        <div
          role="status"
          className="flex items-center gap-2 rounded-control bg-success-bg px-4 py-3 text-sm font-medium text-success shadow-card"
        >
          <CheckCircle2 className="size-5 shrink-0" />
          <span>{thongBaoThanhCong}</span>
        </div>
      )}

      {/* Thông báo lỗi toàn cục (ví dụ: 403 thiếu capability) */}
      {loiChung && (
        <div
          role="alert"
          className="flex items-start gap-2.5 rounded-control bg-danger-bg px-4 py-3 text-sm font-medium text-danger shadow-card"
        >
          <ShieldAlert className="size-5 shrink-0" />
          <p className="flex-1">{loiChung}</p>
        </div>
      )}

      {/* Danh sách tệp */}
      {dangTai && items === null ? (
        <div className="rounded-card border border-line bg-surface p-8 text-center text-sm text-ink-muted">
          Đang tải hàng chờ xác nhận…
        </div>
      ) : items !== null && items.length === 0 ? (
        <div className="rounded-card border border-line bg-surface p-8 text-center text-sm text-ink-muted">
          Không có tệp nào đang chờ xác nhận.
        </div>
      ) : items !== null ? (
        <div className="space-y-3">
          {items.map((t) => {
            const Icon =
              BIEU_TUONG[t.loai_tep as keyof typeof BIEU_TUONG] ?? FileText;
            const urlXem = `/api/cskh/ket-qua/${t.tep_id}/noi-dung`;
            const dangChay = dangXuLy === t.tep_id;
            const loiDong = loiTheoDong[t.tep_id];

            return (
              <article
                key={t.tep_id}
                className="space-y-3 rounded-card border border-line bg-surface p-4 shadow-card"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-line pb-3">
                  <div className="min-w-0">
                    <p className="text-base font-semibold text-ink">
                      {t.ten_khach}{" "}
                      <span className="font-mono text-sm font-normal text-ink-muted">
                        · {t.patient_code}
                      </span>
                    </p>
                    <p className="mt-0.5 text-sm font-medium text-brand-700">
                      Chỉ định: {t.ten_dich_vu}
                    </p>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-chip bg-warning-bg px-2 py-0.5 text-xs font-bold text-warning">
                      {t.xac_nhan_trang_thai}
                    </span>
                    <span className="text-xs text-ink-muted">
                      Tải lên lúc {gioVn(t.tai_len_luc)}
                    </span>
                  </div>
                </div>

                {/* Thông tin tệp và người tải */}
                <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
                  <div className="flex min-w-0 items-center gap-2">
                    <Icon className="size-4 shrink-0 text-ink-muted" />
                    <span className="font-medium text-ink">
                      {t.ten_hien_thi ?? "(Tệp không tên)"}
                    </span>
                    <span className="rounded bg-surface-muted px-1.5 py-0.5 text-xs font-semibold text-ink-soft uppercase">
                      {t.loai_tep}
                    </span>
                    <span className="text-xs text-ink-faint">({t.mime})</span>
                  </div>

                  <div className="text-xs text-ink-soft">
                    Người tải:{" "}
                    <span className="font-semibold text-ink">
                      {t.tai_len_boi_ten ?? "Không rõ"}
                    </span>
                    {t.tai_len_boi_vai === "PARTNER" ? (
                      <span className="ml-1 text-ink-muted font-medium">· Đối tác</span>
                    ) : t.tai_len_boi_vai ? (
                      <span className="ml-1 text-ink-muted">({t.tai_len_boi_vai})</span>
                    ) : null}
                  </div>
                </div>

                {/* Nút xem tệp & Action buttons */}
                <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                  <a
                    href={urlXem}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-sm font-semibold text-brand-700 hover:underline"
                  >
                    <ExternalLink className="size-4" />
                    Mở xem tệp
                  </a>

                  <div className="flex flex-wrap items-center gap-2">
                    {!t.co_the_xac_nhan ? (
                      <span className="rounded-control bg-surface-muted px-3 py-1.5 text-xs font-medium text-ink-muted">
                        {t.khong_the_xac_nhan_ly_do ??
                          "Bạn là người tải tệp này — cần người khác xác nhận."}
                      </span>
                    ) : (
                      <>
                        <button
                          type="button"
                          disabled={dangChay}
                          onClick={() => void xacNhan(t.tep_id, "HOP_LE")}
                          className="inline-flex min-h-9 items-center gap-1.5 rounded-control bg-brand-600 px-4 text-xs font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
                        >
                          <Check className="size-3.5" strokeWidth={3} />
                          {dangChay ? "Đang xử lý…" : "HỢP LỆ"}
                        </button>

                        <button
                          type="button"
                          disabled={dangChay}
                          onClick={() => moHopThoaiTuChoi(t.tep_id)}
                          className="inline-flex min-h-9 items-center gap-1.5 rounded-control border border-danger/40 bg-surface px-4 text-xs font-semibold text-danger hover:bg-danger-bg disabled:opacity-50"
                        >
                          <X className="size-3.5" strokeWidth={3} />
                          TỪ CHỐI
                        </button>
                      </>
                    )}
                  </div>
                </div>

                {loiDong && (
                  <p
                    role="alert"
                    className="flex items-center gap-1.5 text-xs font-medium text-danger"
                  >
                    <AlertCircle className="size-3.5 shrink-0" />
                    {loiDong}
                  </p>
                )}
              </article>
            );
          })}
        </div>
      ) : null}

      {/* Modal / Dialog Từ chối (Bắt buộc lý do) */}
      {tuChoiId && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="tieu-de-tu-choi"
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/70 p-4"
          onClick={() => !dangXuLy && setTuChoiId(null)}
        >
          <div
            className="w-full max-w-md space-y-4 rounded-card bg-surface p-5 shadow-elevated"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-line pb-2">
              <h2 id="tieu-de-tu-choi" className="text-base font-bold text-ink">
                Từ chối tệp kết quả
              </h2>
              <button
                type="button"
                disabled={Boolean(dangXuLy)}
                onClick={() => setTuChoiId(null)}
                className="rounded-control p-1 text-ink-muted hover:bg-surface-muted"
              >
                <X className="size-5" />
              </button>
            </div>

            <p className="text-xs text-ink-muted">
              Tệp bị từ chối sẽ không chuyển sang Bác sĩ đánh giá. Vui lòng ghi rõ lý
              do (sai bệnh nhân, ảnh mờ, thiếu trang, không đúng chỉ định…).
            </p>

            <form onSubmit={xacNhanTuChoiSubmit} className="space-y-3">
              <label className="block">
                <span className="text-xs font-semibold text-ink">
                  Lý do từ chối
                </span>
                <textarea
                  value={lyDoTuChoi}
                  onChange={(e) => {
                    setLyDoTuChoi(e.target.value);
                    if (loiLyDo) setLoiLyDo(null);
                  }}
                  rows={3}
                  placeholder="Ví dụ: Tệp mờ không đọc được thông số, hoặc sai tên bệnh nhân..."
                  className="mt-1 w-full rounded-control border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-brand-500 focus:outline-none"
                  disabled={Boolean(dangXuLy)}
                  autoFocus
                />
              </label>

              {loiLyDo && (
                <p role="alert" className="text-xs font-medium text-danger">
                  {loiLyDo}
                </p>
              )}

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  disabled={Boolean(dangXuLy)}
                  onClick={() => setTuChoiId(null)}
                  className="rounded-control border border-line px-3 py-1.5 text-xs font-medium text-ink-soft hover:bg-surface-muted"
                >
                  Hủy bỏ
                </button>
                <button
                  type="submit"
                  disabled={Boolean(dangXuLy)}
                  className="rounded-control bg-danger px-4 py-1.5 text-xs font-semibold text-white hover:bg-danger/90 disabled:opacity-50"
                >
                  {dangXuLy ? "Đang ghi…" : "Xác nhận từ chối"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </section>
  );
}
