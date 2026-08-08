"use client";

// VÙNG LÀM VIỆC CỦA MỘT KHÁCH — chuỗi bước nối tiếp nhau, không phải một ô
// trạng thái.
//
// Quang (08/08/2026): *"các trạng thái là timeline nối tiếp nhau và ấn vào node
// được, xong rồi thì tích xanh để đó không ẩn, chứ không phải chỉ hiện trạng
// thái, để CSKH còn biết họ đã thao tác gì, mấy giờ."*
//
// VÌ SAO MỘT Ô TRẠNG THÁI LÀ KHÔNG ĐỦ. Ô ấy trả lời "khách này đang ở đâu", và
// mỗi lần CSKH làm xong một việc thì việc đó BIẾN MẤT khỏi màn hình — thay bằng
// việc kế tiếp. Nên đến chiều, người trực ca sau nhìn vào không biết sáng nay
// đã ai gọi chưa, gọi lúc mấy giờ, khách nói gì. Họ gọi lại. Khách nghe máy hai
// lần trong một buổi.
//
// Chuỗi bước thì giữ nguyên cả quá khứ: bước xong mang dấu tích, giờ, tên người
// làm và câu khách nói. Bước đang tới thì bấm được.

import { useState } from "react";
import { Check, Phone, CalendarClock, CircleDashed } from "lucide-react";
import type { DongLichSu } from "./GhiTuongTac";
import TepKetQuaMau from "./TepKetQuaMau";

export interface BuocLamViec {
  /** Mã việc — khớp `loai` của tuong_tac_cskh khi bước này bấm được. */
  ma: string;
  ten: string;
  /** Việc này CSKH tự làm được (bấm để ghi), hay chỉ là mốc hệ thống sinh ra. */
  bam_duoc: boolean;
}

/** Chuỗi bước của một lượt khám, theo đúng thứ tự đời thật.
 *
 *  KHÔNG khai "sau sinh 1 tháng" / "sau thủ thuật 1 ngày" vào đây: hệ thống
 *  không có ngày sinh con thật và các dịch vụ thủ thuật đang tắt, nên hai bước
 *  ấy sẽ đứng xám vĩnh viễn ở cuối mọi chuỗi. Chúng đi qua nút "Hẹn gọi lại". */
const CHUOI_BINH_THUONG: BuocLamViec[] = [
  { ma: "DAT_LICH", ten: "Đặt lịch", bam_duoc: false },
  { ma: "XAC_NHAN_LICH", ten: "Gọi xác nhận lịch", bam_duoc: true },
  { ma: "NHAC_HEN", ten: "Gọi nhắc hẹn", bam_duoc: true },
  { ma: "DEN_KHAM", ten: "Khách đến khám", bam_duoc: false },
  { ma: "CHECK_XN", ten: "Hỏi đơn vị xét nghiệm", bam_duoc: true },
  { ma: "TRA_KQ", ten: "Gọi trả kết quả", bam_duoc: true },
];

/** Lịch đã huỷ đi một nhánh khác hẳn — nối tiếp chuỗi trên là nói dối. */
const CHUOI_HUY: BuocLamViec[] = [
  { ma: "DAT_LICH", ten: "Đặt lịch", bam_duoc: false },
  { ma: "HUY_LICH", ten: "Huỷ lịch", bam_duoc: false },
  { ma: "HOI_LY_DO_HUY", ten: "Gọi hỏi lý do huỷ", bam_duoc: true },
];

function gio(iso: string): string {
  return new Date(iso).toLocaleString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  });
}

const NHAN_KET_QUA: Record<string, string> = {
  DA_LIEN_HE: "đã liên hệ được",
  CHUA_NGHE_MAY: "không nghe máy",
  KHONG_LIEN_LAC_DUOC: "không liên lạc được",
  HEN_GOI_LAI: "khách hẹn gọi lại",
  CAN_BAC_SI: "cần hỏi bác sĩ",
  TU_CHOI: "khách từ chối",
  BO_QUA: "bỏ qua",
};

export interface MocLich {
  /** Lịch hẹn đại diện đang xem. */
  id: string | null;
  status: string | null;
  slot_start: string | null;
  created_at: string | null;
  cancelled_at: string | null;
}

export default function VungLamViecKhach({
  tenKhach,
  lich,
  lichSu,
  onLamViec,
}: {
  tenKhach: string;
  lich: MocLich;
  lichSu: DongLichSu[];
  /** Bấm vào một bước chưa xong → mở ô ghi kết quả với đúng loại việc ấy. */
  onLamViec: (maViec: string) => void;
}) {
  const [moRong, setMoRong] = useState<string | null>(null);

  const daHuy = lich.status === "CANCELLED";
  const chuoi = daHuy ? CHUOI_HUY : CHUOI_BINH_THUONG;

  // Bước nào đã xong, và xong lúc nào. Mốc hệ thống lấy từ chính lịch hẹn; việc
  // CSKH lấy từ sổ tương tác — cùng một câu hỏi, hai nguồn, và cả hai đều là
  // sự thật đã xảy ra chứ không phải cờ ai đó bấm.
  function xongLuc(ma: string): DongLichSu[] {
    if (ma === "DAT_LICH" || ma === "HUY_LICH" || ma === "DEN_KHAM") return [];
    return lichSu.filter((d) => d.loai === ma);
  }
  function mocHeThong(ma: string): string | null {
    if (ma === "DAT_LICH") return lich.created_at;
    if (ma === "HUY_LICH") return lich.cancelled_at;
    return null;
  }
  // `appointment` KHÔNG có cột checked_in_at — chỉ có confirmed_at, cancelled_at,
  // created_at. Nên bước "khách đến khám" biết là ĐÃ XONG mà không biết mấy giờ.
  // Nói đúng cái mình biết: tích xanh, không bịa một con số giờ.
  function daDenKham(): boolean {
    return lich.status === "CHECKED_IN" || lich.status === "COMPLETED";
  }

  const trangThaiBuoc = chuoi.map((b) => {
    const lan = xongLuc(b.ma);
    const moc = mocHeThong(b.ma);
    const xong =
      lan.length > 0 || Boolean(moc) || (b.ma === "DEN_KHAM" && daDenKham());
    return { buoc: b, lan, moc, xong };
  });
  // Bước đang tới = bước CHƯA xong đầu tiên mà CSKH bấm được.
  const dangToi = trangThaiBuoc.find((t) => !t.xong && t.buoc.bam_duoc)?.buoc.ma;

  return (
    <section
      aria-label={`Vùng làm việc — ${tenKhach}`}
      className="min-w-0 overflow-hidden rounded-2xl border border-line bg-surface shadow-card"
    >
      <div className="border-b border-line px-4 py-3">
        <h2 className="text-sm font-semibold text-ink">
          Vùng làm việc — {tenKhach}
        </h2>
        <p className="mt-0.5 text-xs text-ink-muted">
          Bấm vào bước còn sáng để ghi lại việc vừa làm. Bước đã xong ở lại đây
          kèm giờ và người làm.
        </p>
      </div>

      <ol className="space-y-0 px-4 py-3">
        {trangThaiBuoc.map((t, i) => {
          const cuoi = i === trangThaiBuoc.length - 1;
          const la_dang_toi = t.buoc.ma === dangToi;
          const bamDuoc = t.buoc.bam_duoc;
          const mo = moRong === t.buoc.ma;

          return (
            <li key={t.buoc.ma} className="flex gap-3">
              {/* Cột trái: chấm + đoạn nối. Đoạn nối là thứ làm cho chuỗi này
                  đọc thành một hành trình chứ không phải một danh sách rời. */}
              <div className="flex flex-col items-center">
                <span
                  className={`flex size-7 shrink-0 items-center justify-center rounded-full border-2 ${
                    t.xong
                      ? "border-success bg-success-bg text-success"
                      : la_dang_toi
                        ? "border-brand-600 bg-brand-50 text-brand-700"
                        : "border-line bg-surface-muted text-ink-faint"
                  }`}
                >
                  {t.xong ? (
                    <Check className="size-4" strokeWidth={3} />
                  ) : la_dang_toi ? (
                    <Phone className="size-3.5" />
                  ) : (
                    <CircleDashed className="size-3.5" />
                  )}
                </span>
                {!cuoi && (
                  <span
                    className={`w-0.5 flex-1 ${t.xong ? "bg-success" : "bg-line"}`}
                    style={{ minHeight: 18 }}
                  />
                )}
              </div>

              {/* Cột phải: tên bước + những gì đã xảy ra ở đó. */}
              <div className={`min-w-0 flex-1 ${cuoi ? "pb-1" : "pb-4"}`}>
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`text-sm ${
                      t.xong
                        ? "font-medium text-ink"
                        : la_dang_toi
                          ? "font-semibold text-brand-700"
                          : "text-ink-faint"
                    }`}
                  >
                    {t.buoc.ten}
                  </span>

                  {t.moc && (
                    <span className="font-mono text-[11px] text-ink-muted">
                      {gio(t.moc)}
                    </span>
                  )}

                  {la_dang_toi && (
                    <button
                      type="button"
                      onClick={() => onLamViec(t.buoc.ma)}
                      className="rounded-full bg-brand-600 px-2.5 py-0.5 text-[11px] font-semibold text-white hover:bg-brand-700"
                    >
                      Làm bước này
                    </button>
                  )}

                  {/* Bước đã xong vẫn bấm lại được: gọi lần hai là chuyện thật,
                      và ép người ta ghi đè lần một là mất một cuộc gọi. */}
                  {t.xong && bamDuoc && (
                    <button
                      type="button"
                      onClick={() => onLamViec(t.buoc.ma)}
                      className="rounded-full border border-line px-2.5 py-0.5 text-[11px] font-medium text-ink-soft hover:bg-surface-muted"
                    >
                      Làm lại
                    </button>
                  )}
                </div>

                {/* Mỗi lần làm là một dòng — đây là chỗ CSKH đọc "đã thao tác
                    gì, mấy giờ". Quá hai lần thì gấp lại cho gọn. */}
                {t.lan.length > 0 && (
                  <ul className="mt-1 space-y-0.5">
                    {(mo ? t.lan : t.lan.slice(0, 2)).map((d, k) => (
                      <li
                        key={`${d.xay_ra_luc}-${k}`}
                        className="text-[11px] leading-snug text-ink-soft"
                      >
                        <span className="font-mono text-ink-muted">
                          {gio(d.xay_ra_luc)}
                        </span>
                        {d.ket_qua && ` · ${NHAN_KET_QUA[d.ket_qua] ?? d.ket_qua}`}
                        {d.khach_xac_nhan === true && " · khách nói sẽ đến"}
                        {d.nhan_vien && ` · ${d.nhan_vien}`}
                        {d.noi_dung && (
                          <span className="block italic text-ink-muted">
                            “{d.noi_dung}”
                          </span>
                        )}
                      </li>
                    ))}
                    {t.lan.length > 2 && (
                      <li>
                        <button
                          type="button"
                          onClick={() => setMoRong(mo ? null : t.buoc.ma)}
                          className="text-[11px] font-medium text-brand-700 hover:underline"
                        >
                          {mo ? "Thu gọn" : `Xem cả ${t.lan.length} lần`}
                        </button>
                      </li>
                    )}
                  </ul>
                )}
              </div>
            </li>
          );
        })}
      </ol>

      <TepKetQuaMau />

      {lich.slot_start && (
        <p className="flex items-center gap-1.5 border-t border-line px-4 py-2 text-[11px] text-ink-muted">
          <CalendarClock className="size-3.5" />
          Giờ khám: {gio(lich.slot_start)}
          {daHuy && " · lịch này đã huỷ"}
        </p>
      )}
    </section>
  );
}
