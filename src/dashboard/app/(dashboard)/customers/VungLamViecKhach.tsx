"use client";

// VÙNG LÀM VIỆC CỦA MỘT KHÁCH — trọn hành trình, và CSKH bấm được TẤT CẢ.
//
// Quang (08/08/2026): *"cskh đặt lịch rồi này, xong gọi xác nhận trước 7 ngày
// này, gọi nhắc hẹn này, khách đến thì check-in cho khách này, hỏi đơn vị xét
// nghiệm, gọi để trả kết quả, khách checkout, khách đã thanh toán, khách đã mua
// thuốc… tất cả là các nút và thao tác được thật nhé, vì sản phẩm MVP này là
// cskh thao tác được hết mà."*
//
// Hai loại bước, hai cách bấm:
//   · CUỘC GỌI  → mở ô ghi kết quả (ai nghe máy, khách nói gì)
//   · MỐC QUẦY  → một chạm "ghi nhận" — và với check-in / check-out thì backend
//     chạy đúng hành động THẬT trên lịch hẹn: mở lượt khám vào hàng đợi tiếp
//     nhận, hoặc đóng trạng thái khám. Không phải cờ riêng chỉ màn này thấy.
//
// Bước xong tích xanh và Ở LẠI, kèm giờ + người làm. Mọi bước CHƯA xong đều
// bấm được — đời thật không đi đúng thứ tự: khách chưa từng được gọi nhắc vẫn
// có thể đang đứng ở quầy chờ check-in, và chặn CSKH lúc đó là chặn sai người.

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Check,
  Phone,
  CalendarClock,
  CircleDashed,
  Stethoscope,
} from "lucide-react";
import type { DongLichSu } from "./GhiTuongTac";
import TepKetQua, { type TepKetQuaRow } from "./TepKetQua";

interface Buoc {
  ma: string;
  ten: string;
  /** 'goi' mở ô ghi kết quả; 'moc' là một chạm tại quầy; 'he_thong' chỉ xem. */
  kieu: "goi" | "moc" | "he_thong";
}

/** Chuỗi bước của một lượt khám — đúng thứ tự Quang kể.
 *
 *  KHÔNG khai "sau sinh 1 tháng" / "sau thủ thuật 1 ngày": hệ thống không có
 *  ngày sinh con thật nên hai bước ấy sẽ đứng xám vĩnh viễn ở cuối mọi chuỗi.
 *  Chúng đi qua nút "Hẹn gọi lại". */
const CHUOI_BINH_THUONG: Buoc[] = [
  { ma: "DAT_LICH", ten: "Đặt lịch", kieu: "he_thong" },
  { ma: "XAC_NHAN_LICH", ten: "Gọi xác nhận lịch", kieu: "goi" },
  { ma: "NHAC_HEN", ten: "Gọi nhắc hẹn", kieu: "goi" },
  { ma: "CHECK_IN", ten: "Check-in cho khách", kieu: "moc" },
  { ma: "CHECK_XN", ten: "Hỏi đơn vị xét nghiệm", kieu: "goi" },
  { ma: "TRA_KQ", ten: "Gọi trả kết quả", kieu: "goi" },
  { ma: "CHECK_OUT", ten: "Khách check-out", kieu: "moc" },
  { ma: "THANH_TOAN", ten: "Khách đã thanh toán", kieu: "moc" },
  { ma: "MUA_THUOC", ten: "Khách đã mua thuốc", kieu: "moc" },
];

/** Lịch đã huỷ đi một nhánh khác hẳn — nối tiếp chuỗi trên là nói dối. */
const CHUOI_HUY: Buoc[] = [
  { ma: "DAT_LICH", ten: "Đặt lịch", kieu: "he_thong" },
  { ma: "HUY_LICH", ten: "Huỷ lịch", kieu: "he_thong" },
  { ma: "HOI_LY_DO_HUY", ten: "Gọi hỏi lý do huỷ", kieu: "goi" },
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
  CAN_BAC_SI: "cần bác sĩ xem xét",
  TU_CHOI: "khách từ chối",
  BO_QUA: "bỏ qua",
  GHI_NHAN: "đã ghi nhận",
};

export interface MocLich {
  /** Lịch hẹn đại diện đang xem. */
  id: string | null;
  status: string | null;
  slot_start: string | null;
  created_at: string | null;
  cancelled_at: string | null;
}

type TrangThaiNode = "xong" | "cho_bac_si" | "dang_toi" | "cho";

export default function VungLamViecKhach({
  tenKhach,
  clinicPatientId,
  lich,
  lichSu,
  tepKetQua,
  onLamViec,
  children,
}: {
  tenKhach: string;
  clinicPatientId: string;
  lich: MocLich;
  lichSu: DongLichSu[];
  tepKetQua: TepKetQuaRow[];
  /** Bấm một bước CUỘC GỌI → mở ô ghi kết quả với đúng loại việc ấy. */
  onLamViec: (maViec: string) => void;
  /** Khối gắn thêm dưới chuỗi bước (phản hồi khách…). */
  children?: React.ReactNode;
}) {
  const router = useRouter();
  const [moRong, setMoRong] = useState<string | null>(null);
  const [dangGhiMoc, setDangGhiMoc] = useState<string | null>(null);
  const [loiMoc, setLoiMoc] = useState<{ ma: string; loi: string } | null>(null);

  const daHuy = lich.status === "CANCELLED";
  const chuoi = daHuy ? CHUOI_HUY : CHUOI_BINH_THUONG;

  function cacLan(ma: string): DongLichSu[] {
    return lichSu.filter((d) => d.loai === ma);
  }
  function mocHeThong(ma: string): string | null {
    if (ma === "DAT_LICH") return lich.created_at;
    if (ma === "HUY_LICH") return lich.cancelled_at;
    return null;
  }
  // `appointment` không có cột checked_in_at — TRẠNG THÁI là thứ đáng tin (lễ
  // tân có thể đã check-in từ màn khác). Dòng sổ, nếu có, cho thêm giờ và tên.
  function xongTheoTrangThai(ma: string): boolean {
    if (ma === "CHECK_IN") {
      return lich.status === "CHECKED_IN" || lich.status === "COMPLETED";
    }
    if (ma === "CHECK_OUT") return lich.status === "COMPLETED";
    return false;
  }

  const cacBuoc = chuoi.map((b) => {
    const lan = cacLan(b.ma);
    const moc = mocHeThong(b.ma);
    const xong = lan.length > 0 || Boolean(moc) || xongTheoTrangThai(b.ma);
    // "Bác sĩ xem xét, trả sau": lần trả kết quả gần nhất bị dừng ở cửa chuyên
    // môn thì node đứng VÀNG chứ không xanh — việc CHƯA xong, nó đang chờ
    // người khác, và màu phải nói đúng điều đó.
    const choBacSi =
      b.ma === "TRA_KQ" && lan.length > 0 && lan[0].ket_qua === "CAN_BAC_SI";
    return { buoc: b, lan, moc, xong, choBacSi };
  });
  const maDangToi = cacBuoc.find(
    (t) => !t.xong && t.buoc.kieu !== "he_thong",
  )?.buoc.ma;

  async function ghiMoc(ma: string) {
    setDangGhiMoc(ma);
    setLoiMoc(null);
    const res = await fetch("/api/cskh/tuong-tac", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        clinic_patient_id: clinicPatientId,
        appointment_id: lich.id,
        loai: ma,
        kenh: "TRUC_TIEP",
        ket_qua: "GHI_NHAN",
      }),
    });
    setDangGhiMoc(null);
    if (!res.ok) {
      const d = (await res.json().catch(() => null)) as
        | { error?: string; message?: string }
        | null;
      // "Khách chưa check-in — check-in trước rồi mới check-out được" phải
      // hiện NGAY TẠI node vừa bấm, không phải một toast trôi mất.
      setLoiMoc({ ma, loi: d?.message ?? d?.error ?? "Không ghi được." });
      return;
    }
    router.refresh();
  }

  function trangThaiNode(t: (typeof cacBuoc)[number]): TrangThaiNode {
    if (t.choBacSi) return "cho_bac_si";
    if (t.xong) return "xong";
    if (t.buoc.ma === maDangToi) return "dang_toi";
    return "cho";
  }

  return (
    <div className="min-w-0 space-y-3">
      <section
        aria-label={`Vùng làm việc — ${tenKhach}`}
        className="min-w-0 overflow-hidden rounded-2xl border border-line bg-surface shadow-card"
      >
        <div className="border-b border-line px-4 py-3">
          <h2 className="text-sm font-semibold text-ink">
            Vùng làm việc — {tenKhach}
          </h2>
          <p className="mt-0.5 text-xs text-ink-muted">
            Bấm vào bước để làm. Bước đã xong ở lại đây kèm giờ và người làm.
          </p>
        </div>

        <ol className="px-4 py-3">
          {cacBuoc.map((t, i) => {
            const cuoi = i === cacBuoc.length - 1;
            const tt = trangThaiNode(t);
            const mo = moRong === t.buoc.ma;
            const laGoi = t.buoc.kieu === "goi";
            const laMoc = t.buoc.kieu === "moc";
            // Check-in / check-out cần một lịch hẹn để đổi trạng thái thật.
            const thieuLich =
              laMoc &&
              !lich.id &&
              (t.buoc.ma === "CHECK_IN" || t.buoc.ma === "CHECK_OUT");

            return (
              <li key={t.buoc.ma} className="flex gap-3">
                <div className="flex flex-col items-center">
                  <span
                    className={`flex size-7 shrink-0 items-center justify-center rounded-full border-2 ${
                      tt === "xong"
                        ? "border-success bg-success-bg text-success"
                        : tt === "cho_bac_si"
                          ? "border-warning bg-warning-bg text-warning"
                          : tt === "dang_toi"
                            ? "border-brand-600 bg-brand-50 text-brand-700"
                            : "border-line bg-surface-muted text-ink-faint"
                    }`}
                  >
                    {tt === "xong" ? (
                      <Check className="size-4" strokeWidth={3} />
                    ) : tt === "cho_bac_si" ? (
                      <Stethoscope className="size-3.5" />
                    ) : tt === "dang_toi" && laGoi ? (
                      <Phone className="size-3.5" />
                    ) : (
                      <CircleDashed className="size-3.5" />
                    )}
                  </span>
                  {!cuoi && (
                    <span
                      className={`w-0.5 flex-1 ${tt === "xong" ? "bg-success" : "bg-line"}`}
                      style={{ minHeight: 16 }}
                    />
                  )}
                </div>

                <div className={`min-w-0 flex-1 ${cuoi ? "pb-1" : "pb-3.5"}`}>
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`text-sm ${
                        tt === "xong"
                          ? "font-medium text-ink"
                          : tt === "cho_bac_si"
                            ? "font-semibold text-warning"
                            : tt === "dang_toi"
                              ? "font-semibold text-brand-700"
                              : "text-ink-soft"
                      }`}
                    >
                      {t.buoc.ten}
                    </span>

                    {tt === "cho_bac_si" && (
                      <span className="rounded-full bg-warning-bg px-2 py-0.5 text-[10px] font-bold text-warning">
                        chờ bác sĩ xem xét
                      </span>
                    )}

                    {t.moc && (
                      <span className="font-mono text-[11px] text-ink-muted">
                        {gio(t.moc)}
                      </span>
                    )}

                    {/* CUỘC GỌI: mọi bước chưa xong đều bấm được; bước gợi ý
                        nổi hơn. Bước xong vẫn "Làm lại" — gọi lần hai là chuyện
                        thật. Bước chờ-bác-sĩ có "Trả lại sau". */}
                    {laGoi &&
                      (t.xong ? (
                        <button
                          type="button"
                          onClick={() => onLamViec(t.buoc.ma)}
                          className="rounded-full border border-line px-2.5 py-0.5 text-[11px] font-medium text-ink-soft hover:bg-surface-muted"
                        >
                          {tt === "cho_bac_si" ? "Trả lại sau" : "Làm lại"}
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => onLamViec(t.buoc.ma)}
                          className={
                            tt === "dang_toi"
                              ? "rounded-full bg-brand-600 px-2.5 py-0.5 text-[11px] font-semibold text-white hover:bg-brand-700"
                              : "rounded-full border border-brand-300 px-2.5 py-0.5 text-[11px] font-medium text-brand-700 hover:bg-brand-50"
                          }
                        >
                          Làm bước này
                        </button>
                      ))}

                    {/* MỐC QUẦY: một chạm. Xong là xong — không "làm lại" một
                        lần check-in. */}
                    {laMoc && !t.xong && (
                      <button
                        type="button"
                        onClick={() => void ghiMoc(t.buoc.ma)}
                        disabled={dangGhiMoc !== null || thieuLich}
                        title={
                          thieuLich ? "Khách chưa có lịch hẹn nào" : undefined
                        }
                        className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold disabled:opacity-50 ${
                          tt === "dang_toi"
                            ? "bg-brand-600 text-white hover:bg-brand-700"
                            : "border border-brand-300 text-brand-700 hover:bg-brand-50"
                        }`}
                      >
                        {dangGhiMoc === t.buoc.ma ? "Đang ghi…" : "✓ Ghi nhận"}
                      </button>
                    )}
                  </div>

                  {loiMoc?.ma === t.buoc.ma && (
                    <p className="mt-1 text-[11px] text-danger">{loiMoc.loi}</p>
                  )}

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
                          {d.ket_qua &&
                            ` · ${NHAN_KET_QUA[d.ket_qua] ?? d.ket_qua}`}
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

        <TepKetQua
          clinicPatientId={clinicPatientId}
          appointmentId={lich.id}
          items={tepKetQua}
        />

        {lich.slot_start && (
          <p className="flex items-center gap-1.5 border-t border-line px-4 py-2 text-[11px] text-ink-muted">
            <CalendarClock className="size-3.5" />
            Giờ khám: {gio(lich.slot_start)}
            {daHuy && " · lịch này đã huỷ"}
          </p>
        )}
      </section>

      {children}
    </div>
  );
}
