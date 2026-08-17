"use client";

// Lịch sử các lần khám — dạng chuỗi, không phải danh sách phẳng.
//
// QUANG 10/08/2026: timeline dọc trên xuống, hiện những trạng thái CSKH đã bấm
// ở lần trước, có giờ bắt đầu và kết thúc. Và điều quan trọng nhất: *"nếu là
// timeline tái khám, thì lần tái khám sẽ là nối tiếp của lần khám trước, còn
// khám xong rồi hoặc khám mới thì nó là lịch sử riêng"*.
//
// MỘT CHUỖI = MỘT CÂU CHUYỆN. Khách khám phụ khoa tháng 3 rồi tái khám tháng 4
// là một chuyện; tháng 9 khám nội tiết là chuyện khác. Trộn cả hai vào một danh
// sách theo ngày thì người đọc phải tự đoán đâu là nối tiếp, đâu là bắt đầu
// lại — và họ sẽ đoán sai đúng lúc cần nhất.
//
// CHUỖI DỰNG TỪ `appointment.lich_truoc_id` (20260810000007), không suy diễn từ
// "cùng dịch vụ, gần ngày nhau". Xem migration ấy để biết vì sao suy diễn sai.

import { Clock, CircleDashed, Check } from "lucide-react";
import { nhanLyDoHuy } from "@/lib/ly-do-huy";
import type { ChuoiKham, LuotKham } from "./CustomersView";

const NHAN_TRANG_THAI: Record<string, string> = {
  SCHEDULED: "Mới đặt",
  CSKH_CONFIRMED: "CSKH đã xác nhận",
  CONFIRMED: "Đã đặt lịch",
  CHECKED_IN: "Đã check-in",
  COMPLETED: "Khám xong",
  CANCELLED: "Đã huỷ",
  NO_SHOW: "Khách không đến",
  DOCTOR_DECLINED: "Bác sĩ từ chối",
};

/** Tên tiếng Việt của một bước CSKH đã bấm. Ưu tiên `trang_thai_ma` vì đó là
 *  thứ người dùng thật sự bấm; rơi về `loai` cho những dòng ghi trước migration
 *  20260810000002 (hồi ấy chưa có cột ấy). */
const NHAN_BUOC: Record<string, string> = {
  // BA MÃ NÀY VIEW SINH RA VÀ CSKH BẤM ĐƯỢC, mà bảng này thiếu tới 10/08/2026 —
  // nên dòng sổ của chúng rơi vào nhánh `?? b.trang_thai_ma` và in MÃ TRẦN
  // (`HEN_GOI_LAI`, `MOI_TAI_KHAM`…) ngay trong lịch sử khám của khách.
  HEN_GOI_LAI: "Khách hẹn gọi lại",
  MOI_TAI_KHAM: "Gọi mời tái khám",
  NHAC_DI_KHAM: "Gọi nhắc đi khám",
  // Mã do màn Chờ xếp bác sĩ ghi vào sổ khi quản lý đổi giờ.
  QUAN_LY_DOI_GIO: "Quản lý đổi giờ hẹn",
  CHO_XAC_NHAN: "Gọi xác nhận lịch",
  NHAC_HEN_MAI: "Gọi nhắc hẹn",
  DA_CHECKIN: "Check-in",
  CHO_KQ_XN: "Hỏi kết quả xét nghiệm",
  CHO_BAC_SI: "Chờ bác sĩ duyệt kết quả",
  KQ_CHUA_GUI: "Gửi kết quả cho khách",
  DA_TRA_KQ: "Đã trả kết quả",
  GOI_LAI: "Gọi lại",
  HOI_LY_DO_HUY: "Hỏi lý do huỷ",
  KHONG_FOLLOW_UP: "Không cần follow up",
  SAU_SINH_1_THANG: "Gọi sau sinh 1 tháng",
  SAU_THU_THUAT_1_NGAY: "Gọi sau thủ thuật 1 ngày",
  CHECK_IN: "Check-in",
  CHECK_OUT: "Checkout",
  XAC_NHAN_LICH: "Gọi xác nhận lịch",
  NHAC_HEN: "Gọi nhắc hẹn",
  TRA_KQ: "Trả kết quả",
  CHECK_XN: "Hỏi kết quả xét nghiệm",
};

const NHAN_KET_QUA: Record<string, string> = {
  DA_LIEN_HE: "đã liên hệ được",
  CHUA_NGHE_MAY: "không nghe máy",
  KHONG_LIEN_LAC_DUOC: "không liên lạc được",
  HEN_GOI_LAI: "khách hẹn gọi lại",
  CAN_BAC_SI: "cần bác sĩ xem xét",
  TU_CHOI: "khách từ chối",
  BO_QUA: "bỏ qua",
  GHI_NHAN: "đã ghi nhận",
};

function gio(iso: string): string {
  return new Date(iso).toLocaleString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  });
}

function khoangThoiGian(luot: LuotKham): string {
  if (!luot.bat_dau) return "chưa check-in";
  if (!luot.ket_thuc) return `${gio(luot.bat_dau)} → chưa đóng`;
  return `${gio(luot.bat_dau)} → ${gio(luot.ket_thuc)}`;
}

function MotLuot({
  luot,
  thuTu,
  dangXem,
  onChon,
}: {
  luot: LuotKham;
  thuTu: number;
  /** Lượt này có đang là lượt ba cột đang làm việc trên đó không. */
  dangXem: boolean;
  /** Bấm để chuyển sang làm việc trên lượt này. Không truyền = chỉ đọc. */
  onChon?: (id: string) => void;
}) {
  const xong = luot.status === "COMPLETED";
  const chet = ["CANCELLED", "NO_SHOW", "DOCTOR_DECLINED"].includes(luot.status);

  return (
    <li className="flex gap-3">
      <div className="flex flex-col items-center">
        <span
          className={`flex size-6 shrink-0 items-center justify-center rounded-full border-2 text-label font-bold ${
            xong
              ? "border-success bg-success-bg text-success"
              : chet
                ? "border-line bg-surface-muted text-ink-faint"
                : "border-brand-500 bg-brand-50 text-brand-700"
          }`}
        >
          {xong ? <Check className="size-3" strokeWidth={3} /> : thuTu}
        </span>
        <span className="w-0.5 flex-1 bg-line" style={{ minHeight: 8 }} />
      </div>

      <div
        className={`min-w-0 flex-1 pb-3 ${
          dangXem ? "-mx-1.5 rounded-lg bg-brand-50/60 px-1.5" : ""
        }`}
      >
        <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
          <span className="text-xs font-semibold text-ink">
            {luot.service_name || "Chưa chọn dịch vụ"}
          </span>
          <span className="rounded-chip bg-surface-sunken px-1.5 py-0.5 text-label font-medium text-ink-muted">
            {NHAN_TRANG_THAI[luot.status] ?? luot.status}
          </span>
          {thuTu > 1 && (
            <span className="rounded-chip bg-brand-50 px-1.5 py-0.5 text-label font-semibold text-brand-700">
              tái khám lần {thuTu - 1}
            </span>
          )}
          {/* CHỌN LƯỢT ĐỂ LÀM VIỆC.
              Đây là chỗ DUY NHẤT trên màn liệt kê đủ mọi lượt của khách, nên nó
              cũng là chỗ tự nhiên để chuyển lượt. Trước 10/08/2026 không có chỗ
              nào làm được việc ấy: server đoán một "lịch đại diện" cho cả
              khách, và đặt tái khám xong màn vẫn đứng ở lượt cũ. */}
          {dangXem ? (
            <span className="rounded-chip bg-brand-700 px-1.5 py-0.5 text-label font-bold text-white">
              đang làm việc ở lượt này
            </span>
          ) : (
            onChon && (
              <button
                type="button"
                onClick={() => onChon(luot.id)}
                className="rounded-full px-1.5 py-0.5 text-label font-medium text-brand-700 ring-1 ring-inset ring-brand-300 hover:bg-brand-50"
              >
                Làm việc ở lượt này
              </button>
            )
          )}
        </div>

        <p className="mt-0.5 flex items-center gap-1 text-label text-ink-muted">
          <Clock className="size-3 shrink-0" aria-hidden="true" />
          <span className="font-mono">{khoangThoiGian(luot)}</span>
          {luot.doctor_name && <span>· {luot.doctor_name}</span>}
        </p>

        {/* LÝ DO HUỶ, HIỆN Ở ĐÚNG LƯỢT BỊ HUỶ.
            Một đợt có thể gồm ba lượt mà chỉ một lượt bị huỷ — đặt lý do ở
            tiêu đề hộp là gán nhầm lượt. `booking_service` ghi cả mã lẫn chữ
            tự viết từ lâu; màn này chỉ chưa từng đọc chúng. */}
        {chet && (luot.ly_do_huy_ma || luot.cancellation_reason) && (
          <p className="mt-0.5 text-label leading-snug text-ink-soft">
            <span className="font-semibold text-ink-muted">Lý do huỷ: </span>
            {nhanLyDoHuy(luot.ly_do_huy_ma)}
            {luot.cancellation_reason && (
              <span className="block italic">“{luot.cancellation_reason}”</span>
            )}
            {luot.cancelled_at && (
              <span className="block font-mono text-ink-muted">
                huỷ lúc {gio(luot.cancelled_at)}
              </span>
            )}
          </p>
        )}

        {/* CÁC BƯỚC CSKH ĐÃ BẤM trong chính lượt này. Rỗng là bình thường —
            lịch chưa tới, hoặc không ai phải gọi gì cả. Nói ra thay vì để một
            khoảng trắng khó hiểu. */}
        {luot.buoc.length === 0 ? (
          <p className="mt-1 text-label italic text-ink-faint">
            Chưa có thao tác chăm sóc nào trong lượt này.
          </p>
        ) : (
          <ol className="mt-1 space-y-0.5">
            {luot.buoc.map((b, i) => (
              <li
                key={`${b.luc}-${i}`}
                className={`flex items-start gap-1.5 text-label leading-snug ${
                  b.huy_luc ? "text-ink-faint" : "text-ink-soft"
                }`}
              >
                <CircleDashed
                  className="mt-0.5 size-3 shrink-0 text-ink-faint"
                  aria-hidden="true"
                />
                {/* DÒNG ĐÃ RÚT LẠI VẪN HIỆN, chỉ gạch ngang.
                    Quang 10/08/2026: *"log không được xoá, mà là hoàn tác lại
                    tác vụ đó"*. Giấu nó đi là đúng thứ câu ấy cấm — lịch sử
                    phải đọc được cả hai vế: đã bấm, rồi đã rút lại. */}
                <span className={b.huy_luc ? "line-through" : undefined}>
                  <span className="font-mono text-ink-muted">{gio(b.luc)}</span>
                  {" · "}
                  {NHAN_BUOC[b.trang_thai_ma ?? ""] ??
                    NHAN_BUOC[b.loai] ??
                    b.trang_thai_ma ??
                    b.loai}
                  {b.ket_qua &&
                    ` · ${NHAN_KET_QUA[b.ket_qua] ?? b.ket_qua}`}
                  {b.nhan_vien && ` · ${b.nhan_vien}`}
                </span>
                {b.huy_luc && (
                  <span className="shrink-0 rounded-chip bg-surface-sunken px-1.5 text-label font-medium text-ink-muted">
                    đã hoàn tác
                  </span>
                )}
              </li>
            ))}
          </ol>
        )}
      </div>
    </li>
  );
}

export default function LichSuCacLanKham({
  chuoi,
  luotDangXem = null,
  onChonLuot,
}: {
  chuoi: ChuoiKham[];
  /** `appointment.id` của lượt ba cột đang làm việc trên đó. */
  luotDangXem?: string | null;
  onChonLuot?: (id: string) => void;
}) {
  return (
    <section
      aria-label="Lịch sử các lần khám"
      className="rounded-2xl border border-line bg-surface shadow-card"
    >
      <header className="flex items-center justify-between border-b border-line px-4 py-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
          <Clock className="size-4 text-ink-muted" aria-hidden="true" />
          Lịch sử các lần khám
        </h2>
        {chuoi.length > 1 && (
          <span className="text-label text-ink-muted">
            {chuoi.length} đợt khám riêng
          </span>
        )}
      </header>

      <div className="space-y-3 px-4 py-3">
        {chuoi.length === 0 ? (
          <p className="py-2 text-xs text-ink-muted">
            Khách chưa có lượt khám nào.
          </p>
        ) : (
          chuoi.map((c, i) => (
            <div
              key={c.luot[0]?.id ?? i}
              className="rounded-xl border border-line p-3"
            >
              {/* MỖI HỘP LÀ MỘT ĐỢT. Nhiều lượt trong một hộp = chuỗi tái khám
                  nối tiếp nhau; hộp riêng = câu chuyện riêng. */}
              <p className="mb-1.5 text-label font-semibold uppercase tracking-wide text-ink-faint">
                {c.luot.length > 1
                  ? `Đợt ${c.luot[0]?.service_name ?? "khám"} · ${c.luot.length} lượt`
                  : "Khám một lượt"}
              </p>
              <ol>
                {c.luot.map((l, j) => (
                  <MotLuot
                    key={l.id}
                    luot={l}
                    thuTu={j + 1}
                    dangXem={l.id === luotDangXem}
                    onChon={onChonLuot}
                  />
                ))}
              </ol>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
