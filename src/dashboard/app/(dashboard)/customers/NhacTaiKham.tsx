"use client";

// NHẮC TÁI KHÁM — nằm TRONG vùng làm việc của khách, không phải một màn riêng.
//
// VÌ SAO KHỐI NÀY Ở ĐÂY. `/nhac-tai-kham` là một danh sách rời: người bác sĩ
// hẹn quay lại mà chưa đặt lịch. Nó đã bị gỡ khỏi thanh bên của CSKH ngày
// 09/08/2026, và lúc đó chức năng CHƯA được gộp về đâu cả — nên CSKH mất luôn
// đường vào việc gọi mời tái khám. Đây là chỗ nó thuộc về: cùng màn với lịch
// sử, chuỗi bước và phản hồi của chính khách ấy.
//
// VÀ MỘT LỖ HỔNG TO HƠN. Việc gọi nhắc tái khám chỉ sinh ra từ MỘT nguồn:
// `soap_plan.tai_kham.ngay` trong một phiếu khám đã chốt. Khách nói qua điện
// thoại "tháng sau em quay lại" thì không có phiếu nào để đọc — câu ấy không có
// chỗ nào để ghi xuống. Quang chỉ vào đúng chỗ này (09/08/2026):
// *"nhắc tái khám CSKH tự điền vào giai đoạn này, cũng đếm thời gian và trước
// 7 ngày, trước 1 ngày nhớ có action để alo họ"*.
//
// HAI MỐC, KHÔNG PHẢI MỘT:
//   T−7 → gọi MỜI ĐẶT LỊCH   (khách chưa có lịch)
//   T−1 → gọi NHẮC ĐI KHÁM

import { VN_OFFSET } from "../../../lib/datetime";
import { useState } from "react";
import { nhanLoi } from "@/lib/loi-api";
import { useRouter } from "next/navigation";
import {
  CalendarPlus,
  PhoneCall,
  PhoneOff,
  Stethoscope,
  XCircle,
} from "lucide-react";

/** Một mốc gọi đang mở của khách này (bảng `nhac_tai_kham`). */
export interface MocTaiKham {
  id: string;
  luot_goi: number;
  /** Ngày khách được hẹn quay lại. */
  ngay_hen: string;
  /** Ngày PHẢI gọi: lượt 1 = ngay_hen − 7, lượt 2 = ngay_hen − 1 (CSKH nhập). */
  han_goi: string;
  qua_han: boolean;
  ly_do: string | null;
  nguon: string;
}

// Bốn kết quả, không phải một nút "Đã gọi" — cùng bộ từ với `cskh_log.ket_qua`
// và với CHECK ở database. "Chuông đổ không ai bắt" cũng là một việc đã làm, và
// nó phải khác "đã nói chuyện được": không phân biệt thì hôm sau người khác mở
// lên thấy 'đã gọi' rồi bỏ qua một người chưa ai nói chuyện với.
const KET_QUA = [
  { ma: "DA_LIEN_HE", nhan: "Đã liên hệ", Icon: PhoneCall },
  { ma: "CHUA_NGHE_MAY", nhan: "Chưa nghe máy", Icon: PhoneOff },
  { ma: "CAN_BAC_SI", nhan: "Cần bác sĩ", Icon: Stethoscope },
  { ma: "TU_CHOI", nhan: "Khách từ chối", Icon: XCircle },
] as const;

/** Hôm nay theo giờ Việt Nam, dạng yyyy-mm-dd — cùng dạng `han_goi`. */
function homNayVn(): string {
  return new Date(Date.now() + 7 * 3600 * 1000).toISOString().slice(0, 10);
}

function ngayVn(iso: string | null): string {
  if (!iso) return "—";
  const t = Date.parse(iso.length === 10 ? `${iso}T00:00:00` : iso);
  return Number.isFinite(t) ? new Date(t).toLocaleDateString("vi-VN") : "—";
}

/** Số ngày từ hôm nay tới `iso`. Âm = đã qua. So bằng CHUỖI NGÀY, không bằng
 *  `Date` — `new Date("2026-09-15")` là nửa đêm UTC, tức 7 giờ sáng ở Việt Nam,
 *  nên mọi phép trừ lệch đúng một phần ngày. */
function conBaoNhieuNgay(iso: string): number {
  const moc = Date.parse(`${iso}T00:00:00${VN_OFFSET}`);
  const nay = Date.parse(`${homNayVn()}T00:00:00${VN_OFFSET}`);
  return Math.round((moc - nay) / 86_400_000);
}

function demNguoc(soNgay: number): string {
  if (soNgay === 0) return "hôm nay";
  if (soNgay === 1) return "ngày mai";
  if (soNgay > 0) return `còn ${soNgay} ngày`;
  return `quá ${-soNgay} ngày`;
}

export default function NhacTaiKham({
  clinicPatientId,
  moc,
}: {
  clinicPatientId: string;
  /** Mốc gọi đang mở của khách này, mới nhất trước. */
  moc: MocTaiKham[];
}) {
  const router = useRouter();
  const [moForm, setMoForm] = useState(false);
  const [ngay, setNgay] = useState("");
  const [lyDo, setLyDo] = useState("");
  const [dangLuu, setDangLuu] = useState(false);
  const [dangGhi, setDangGhi] = useState<string | null>(null);
  const [ghiChu, setGhiChu] = useState<Record<string, string>>({});
  const [loi, setLoi] = useState<string | null>(null);

  async function luuLoiHen() {
    setDangLuu(true);
    setLoi(null);
    try {
      const res = await fetch("/api/cskh/nhac-tai-kham", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          clinic_patient_id: clinicPatientId,
          ngay_tai_kham: ngay,
          ly_do: lyDo.trim() || null,
        }),
      });
      if (!res.ok) {
        const d = (await res.json().catch(() => null)) as {
          error?: string;
          message?: string;
        } | null;
        setLoi(nhanLoi(d, "Không lưu được lời hẹn tái khám."));
        return;
      }
      router.refresh();
      setMoForm(false);
      setNgay("");
      setLyDo("");
    } finally {
      setDangLuu(false);
    }
  }

  async function ghiKetQua(viecId: string, ketQua: string) {
    setDangGhi(viecId);
    setLoi(null);
    try {
      const res = await fetch(`/api/recall-jobs/${viecId}/ket-qua`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ket_qua: ketQua,
          ghi_chu: ghiChu[viecId]?.trim() || null,
        }),
      });
      if (!res.ok) {
        const d = (await res.json().catch(() => null)) as {
          error?: string;
          message?: string;
        } | null;
        setLoi(nhanLoi(d, "Không ghi được kết quả cuộc gọi."));
        return;
      }
      router.refresh();
    } finally {
      setDangGhi(null);
    }
  }

  return (
    <section
      aria-label="Nhắc tái khám"
      className="min-w-0 overflow-hidden rounded-2xl border border-line bg-surface shadow-card"
    >
      <div className="flex items-center justify-between gap-2 border-b border-line px-4 py-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
          <CalendarPlus className="size-4 text-brand-600" aria-hidden="true" />
          Nhắc tái khám
        </h2>
        {!moForm && (
          <button
            type="button"
            onClick={() => setMoForm(true)}
            className="rounded-xl border border-brand-300 px-2.5 py-1 text-label font-semibold text-brand-700 hover:bg-brand-50"
          >
            + Hẹn ngày tái khám
          </button>
        )}
      </div>

      <div className="space-y-3 px-4 py-3">
        {loi && <p className="text-label text-danger">{loi}</p>}

        {moForm && (
          <div className="space-y-2 rounded-xl border border-line bg-surface-muted p-3">
            <label className="block text-label font-medium text-ink-soft">
              Bác sĩ / khách hẹn quay lại ngày
              <input
                type="date"
                value={ngay}
                min={homNayVn()}
                onChange={(e) => setNgay(e.target.value)}
                className="mt-1 w-full rounded-lg border border-line bg-surface px-2 py-1.5 text-xs text-ink"
              />
            </label>
            <input
              value={lyDo}
              onChange={(e) => setLyDo(e.target.value)}
              placeholder="Tái khám để làm gì (VD: kiểm tra lại tuyến giáp)"
              className="w-full rounded-lg border border-line bg-surface px-2 py-1.5 text-xs text-ink"
            />
            {/* Nói TRƯỚC hệ thống sẽ làm gì, thay vì để người dùng lưu xong rồi
                đoán. Hai mốc này là toàn bộ giá trị của việc gõ ngày vào đây. */}
            {ngay && (
              <p className="text-label text-ink-muted">
                Sẽ tự tạo hai việc gọi: <b>{ngayVn(ngay)}</b> là ngày tái khám →
                mời đặt lịch từ <b>{ngayVn(dichNgay(ngay, -7))}</b>, nhắc đi khám
                ngày <b>{ngayVn(dichNgay(ngay, -1))}</b>.
              </p>
            )}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => void luuLoiHen()}
                disabled={dangLuu || !ngay}
                className="flex-1 rounded-lg bg-brand-600 py-1.5 text-xs font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
              >
                {dangLuu ? "Đang lưu…" : "Lưu lời hẹn"}
              </button>
              <button
                type="button"
                onClick={() => setMoForm(false)}
                className="rounded-lg border border-line px-3 py-1.5 text-xs font-medium text-ink-soft hover:bg-surface-muted"
              >
                Huỷ
              </button>
            </div>
          </div>
        )}

        {moc.length === 0 ? (
          !moForm && (
            <p className="text-label text-ink-faint">
              Chưa có lời hẹn tái khám nào cho khách này.
            </p>
          )
        ) : (
          <ul className="space-y-2">
            {moc.map((m) => {
              const conNgay = conBaoNhieuNgay(m.han_goi);
              // ĐẾN HẠN THÌ MỚI MỜI GỌI. Bày bốn nút kết quả cho một việc còn
              // ba tuần nữa mới tới hạn là mời người trực đóng nó cho gọn màn
              // hình — và khách sẽ không được gọi vào đúng ngày cần gọi.
              const toiHan = conNgay <= 0;
              return (
                <li
                  key={m.id}
                  className={`rounded-xl border p-2.5 ${
                    m.qua_han
                      ? "border-danger/40 bg-danger-bg/40"
                      : toiHan
                        ? "border-brand-300 bg-brand-50/50"
                        : "border-line bg-surface-muted/50"
                  }`}
                >
                  <div className="flex flex-wrap items-baseline justify-between gap-x-2 gap-y-1">
                    <span className="text-xs font-semibold text-ink">
                      {m.luot_goi === 1
                        ? "Gọi mời đặt lịch tái khám"
                        : "Gọi nhắc đi khám"}
                    </span>
                    <span
                      className={`text-label font-semibold ${
                        m.qua_han ? "text-danger" : "text-ink-muted"
                      }`}
                    >
                      hạn gọi {ngayVn(m.han_goi)} · {demNguoc(conNgay)}
                    </span>
                  </div>
                  <p className="mt-0.5 text-label text-ink-muted">
                    Tái khám {ngayVn(m.ngay_hen)}
                    {m.ly_do ? ` · ${m.ly_do}` : ""}
                    {m.nguon === "CSKH_NHAP" ? " · CSKH ghi" : " · từ phiếu khám"}
                  </p>

                  {toiHan ? (
                    <div className="mt-2 space-y-1.5">
                      <input
                        value={ghiChu[m.id] ?? ""}
                        onChange={(e) =>
                          setGhiChu((p) => ({ ...p, [m.id]: e.target.value }))
                        }
                        placeholder="Ghi chú cuộc gọi (không bắt buộc)"
                        className="w-full rounded-lg border border-line bg-surface px-2 py-1.5 text-label text-ink"
                      />
                      <div className="flex flex-wrap gap-1.5">
                        {KET_QUA.map(({ ma, nhan, Icon }) => (
                          <button
                            key={ma}
                            type="button"
                            disabled={dangGhi === m.id}
                            onClick={() => void ghiKetQua(m.id, ma)}
                            className="inline-flex items-center gap-1 rounded-lg border border-line bg-surface px-2 py-1 text-label font-medium text-ink-soft hover:bg-surface-muted disabled:opacity-50"
                          >
                            <Icon size={12} />
                            {nhan}
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}

/** `iso` lệch đi `so` ngày, vẫn dạng yyyy-mm-dd. Dựng mốc ở +07:00 để phép
 *  cộng không rơi sang ngày khác vì lệch múi giờ. */
function dichNgay(iso: string, so: number): string {
  const t = Date.parse(`${iso}T00:00:00${VN_OFFSET}`);
  if (!Number.isFinite(t)) return iso;
  return new Date(t + so * 86_400_000).toLocaleDateString("en-CA", {
    timeZone: "Asia/Ho_Chi_Minh",
  });
}
