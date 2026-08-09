"use client";

// TRẠNG THÁI KHÁCH HÀNG — và việc phải làm ứng với từng trạng thái.
//
// ĐÂY LÀ BẢN VIẾT LẠI THEO ĐẶC TẢ CỦA CHỊ THU (Quang họp 09/08/2026). Bản trước
// là một CHUỖI BƯỚC tuyến tính: đặt lịch → gọi xác nhận → nhắc hẹn → check-in →
// hỏi xét nghiệm → trả kết quả → check-out → thanh toán → mua thuốc. Nó sai mô
// hình chứ không sai chi tiết:
//
//   · Một khách KHÔNG đi qua chín bước theo thứ tự. Họ Ở TRONG một trạng thái,
//     và trạng thái ấy quyết định CSKH phải nhấc máy lên làm gì.
//   · Chuỗi tuyến tính không diễn tả được những nhánh có thật: huỷ lịch, không
//     nghe máy, kết quả về nhưng bác sĩ chưa duyệt, sau sinh, sau thủ thuật.
//   · Và nó không nói được "khách này đang ở đâu" — thứ duy nhất người trực ca
//     cần biết khi mở màn hình lên.
//
// Nay: một DANH SÁCH TRẠNG THÁI chia hai giai đoạn (trước khám / sau khám). Bấm
// vào một trạng thái thì khối hành động bên phải đổi tiêu đề VÀ đổi nút theo
// đúng việc của trạng thái ấy — xem HANH_DONG trong HanhDongTrangThai.tsx.
//
// TRẠNG THÁI NÀO MÁY TỰ BIẾT, TRẠNG THÁI NÀO NGƯỜI TỰ CHỌN.
//
// Bảy trạng thái đầu suy được từ dữ liệu thật (view `v_trang_thai_cskh`, trạng
// thái lịch hẹn, sổ tương tác) — chúng tự sáng lên. Ba trạng thái cuối (không
// follow-up sau thủ thuật, sau sinh 1 tháng, sau thủ thuật 1 ngày) KHÔNG có
// nguồn dữ liệu: hệ thống không có ngày sinh con thật (`edd_date` là ngày DỰ
// sinh, lệch hai tuần), và các dịch vụ thủ thuật đang tắt. Chúng vẫn có mặt để
// CSKH tự chọn và ghi lại — một nút người bấm thì có việc THẬT, một tab tự sinh
// từ ngày dự sinh thì có việc SAI mà không ai biết là sai cho tới lúc gọi nhầm.
//
// Mọi thao tác đều ghi sổ: `tuong_tac_cskh` + `event_log` (xem
// TuongTacCskhService.ghi).

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Check,
  Phone,
  CalendarClock,
  CircleDashed,
} from "lucide-react";
import type { DongLichSu } from "./so-tuong-tac";
import TepKetQua, { type TepKetQuaRow } from "./TepKetQua";

/** Một trạng thái khách có thể đang ở, kèm việc CSKH phải làm khi ở đó. */
interface TrangThai {
  ma: string;
  /** Tên trạng thái — phần IN ĐẬM trong đặc tả. */
  ten: string;
  /** Việc phải làm — phần sau mũi tên trong đặc tả. */
  viec: string;
  /** Không suy được từ dữ liệu; CSKH tự chọn khi biết. */
  tuChon?: boolean;
}

const TRUOC_KHAM: TrangThai[] = [
  {
    ma: "CHO_XAC_NHAN",
    ten: "Chờ xác nhận lịch trước 7 ngày",
    viec: "Gọi điện xác nhận lịch với khách",
  },
  {
    ma: "NHAC_HEN_MAI",
    ten: "Cần nhắc hẹn",
    viec: "Gọi nhắc hẹn — khách đã xác nhận, có lịch khám ngày mai",
  },
];

const SAU_KHAM: TrangThai[] = [
  {
    ma: "DA_CHECKIN",
    ten: "Đã check-in",
    viec: "Xem tình trạng sau khám để biết việc tiếp: trả kết quả xét nghiệm hay đặt lịch tái khám",
  },
  {
    ma: "CHO_KQ_XN",
    ten: "Chờ kết quả xét nghiệm",
    viec: "Hỏi đơn vị xét nghiệm xem kết quả về chưa",
  },
  {
    ma: "GOI_LAI",
    ten: "KNM / KLLD / Hẹn GLS",
    viec: "Gọi lại để xác nhận lịch hẹn",
  },
  {
    ma: "CHO_BAC_SI",
    ten: "Có kết quả, chờ phản hồi chuyên môn",
    viec: "Hỏi bác sĩ trước khi trả kết quả cho khách",
  },
  {
    ma: "KQ_CHUA_GUI",
    ten: "Đã có kết quả, chưa gửi",
    viec: "Tải kết quả lên rồi gửi cho khách (ảnh siêu âm, phiếu xét nghiệm — video đang xây dựng)",
  },
  {
    ma: "DA_TRA_KQ",
    ten: "Đã gọi trả kết quả xét nghiệm",
    viec: "Cân nhắc có cần hẹn lịch tái khám sau đó không",
  },
  {
    ma: "HOI_LY_DO_HUY",
    ten: "Huỷ lịch",
    viec: "Gọi lại hỏi lý do huỷ, sau 1–14 ngày. Lý do chọn sẵn hoặc tự viết",
  },
  {
    ma: "KHONG_FOLLOW_UP",
    ten: "Không cần follow up sau thủ thuật",
    viec: "Không gọi vào ngày hôm sau — ghi lại để ca sau khỏi gọi",
    tuChon: true,
  },
  {
    ma: "SAU_SINH_1_THANG",
    ten: "Sau sinh 1 tháng",
    viec: "Chúc mừng đầy tháng, mời khám lại sau sinh",
    tuChon: true,
  },
  {
    ma: "SAU_THU_THUAT_1_NGAY",
    ten: "Sau thủ thuật 1 ngày",
    viec: "Gọi hỏi thăm tình trạng",
    tuChon: true,
  },
];

/** Mốc tại quầy — một chạm, đổi trạng thái THẬT của lịch hẹn.
 *
 *  KHÔNG nằm trong danh sách trạng thái của chị Thu, và cố ý: chúng là VIỆC
 *  XẢY RA tại quầy chứ không phải chỗ khách đang đứng. Nhưng Quang yêu cầu
 *  08/08 (*"khách checkout, khách đã thanh toán, khách đã mua thuốc… tất cả là
 *  các nút và thao tác được thật"*) nên chúng ở lại, gom xuống cuối. */
const MOC_QUAY: { ma: string; ten: string }[] = [
  { ma: "CHECK_IN", ten: "Check-in cho khách" },
  { ma: "CHECK_OUT", ten: "Khách check-out" },
  { ma: "THANH_TOAN", ten: "Khách đã thanh toán" },
  { ma: "MUA_THUOC", ten: "Khách đã mua thuốc" },
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

/** ĐƯỜNG LÙI cho những dòng ghi TRƯỚC migration 20260810000002 — hồi ấy chưa
 *  có cột `trang_thai_ma`, nên chỉ suy được theo `loai`. Bảng này cố ý KHÔNG
 *  liệt kê các trạng thái dùng chung loại `KHAC`: đoán ở đó là tích xanh nhầm
 *  node, tệ hơn là không tích. */
const SUY_THEO_LOAI_CU: Record<string, string[]> = {
  CHO_XAC_NHAN: ["XAC_NHAN_LICH"],
  CHO_KQ_XN: ["CHECK_XN"],
  HOI_LY_DO_HUY: ["HOI_LY_DO_HUY"],
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
  clinicPatientId,
  lich,
  lichSu,
  tepKetQua,
  trangThaiHienTai,
  dangChon,
  onLamViec,
  children,
}: {
  tenKhach: string;
  clinicPatientId: string;
  lich: MocLich;
  lichSu: DongLichSu[];
  tepKetQua: TepKetQuaRow[];
  /** Trạng thái gấp nhất do `v_trang_thai_cskh` suy ra. */
  trangThaiHienTai?: string | null;
  /** Trạng thái CSKH đang chọn làm việc (null = chưa chọn). */
  dangChon?: string | null;
  /** Bấm một trạng thái → khối hành động bên phải đổi theo nó. */
  onLamViec: (maTrangThai: string) => void;
  /** Khối gắn thêm bên dưới (phản hồi khách, nhắc tái khám…). */
  children?: React.ReactNode;
}) {
  const router = useRouter();
  const [dangGhiMoc, setDangGhiMoc] = useState<string | null>(null);
  const [loiMoc, setLoiMoc] = useState<{ ma: string; loi: string } | null>(null);

  const daHuy = lich.status === "CANCELLED";
  const daCheckin =
    lich.status === "CHECKED_IN" || lich.status === "COMPLETED";

  function cacLan(loai: string): DongLichSu[] {
    return lichSu.filter((d) => d.loai === loai);
  }

  /** Trạng thái này đã xong chưa, kể cả khi chưa có dòng sổ nào.
   *
   *  "Đã check-in" xong khi lịch hẹn đã COMPLETED — lễ tân có thể đóng lượt
   *  khám từ màn khác, và node ở đây phải nói đúng chuyện đó. */
  function xongTheoLich(ma: string): boolean {
    if (ma === "DA_CHECKIN") return lich.status === "COMPLETED";
    return false;
  }

  /** Trạng thái này có ĐANG đúng với khách không — suy từ dữ liệu thật. */
  function dangO(ma: string): boolean {
    if (ma === trangThaiHienTai) return true;
    if (ma === "DA_CHECKIN") return daCheckin;
    if (ma === "HOI_LY_DO_HUY") return daHuy;
    if (ma === "DA_TRA_KQ") {
      return cacLan("TRA_KQ").some((d) => d.ket_qua === "DA_LIEN_HE");
    }
    return false;
  }

  /** Lần chạm gần nhất ĐÓNG trạng thái này — cơ sở để node tích xanh.
   *
   *  Dò theo `trang_thai_ma`, cột ghi thẳng mã trạng thái mà thao tác xử lý.
   *  Trước đây dò theo `loai` và nó sai ở cả hai chiều: ba trạng thái cùng ghi
   *  loại `KHAC` nên bấm cái này tích xanh cái kia, còn "không cần follow up"
   *  thì không tích được cái nào. */
  function lanCuoi(ma: string): DongLichSu | undefined {
    const theoMa = lichSu.find((d) => d.trang_thai_ma === ma);
    if (theoMa) return theoMa;
    const loai = SUY_THEO_LOAI_CU[ma];
    return loai ? lichSu.find((d) => loai.includes(d.loai)) : undefined;
  }

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
      // "Khách chưa check-in — check-in trước rồi mới check-out được" phải hiện
      // NGAY TẠI nút vừa bấm, không phải một toast trôi mất.
      setLoiMoc({ ma, loi: d?.message ?? d?.error ?? "Không ghi được." });
      return;
    }
    router.refresh();
  }

  /** MỘT NODE TRÊN TIMELINE.
   *
   *  Quang 09/08/2026: *"tôi không muốn bạn làm dạng ô như này đâu, vẫn là
   *  timeline node như trước khi sửa cơ"*. Nên hình dạng quay lại đúng bản cũ —
   *  vòng tròn viền dày nối nhau bằng một sợi dọc — chỉ có NỘI DUNG là khác:
   *  node bây giờ là TRẠNG THÁI khách đang ở, không phải bước thứ mấy của một
   *  hành trình. */
  function Node({
    tt,
    cuoi,
  }: {
    tt: TrangThai;
    cuoi: boolean;
  }) {
    const dang = dangO(tt.ma);
    const chon = dangChon === tt.ma;
    const lan = lanCuoi(tt.ma);
    const xong = Boolean(lan) || xongTheoLich(tt.ma);

    return (
      <li className="flex gap-3">
        <div className="flex flex-col items-center">
          <span
            className={`flex size-7 shrink-0 items-center justify-center rounded-full border-2 ${
              xong
                ? "border-success bg-success-bg text-success"
                : dang
                  ? "border-brand-600 bg-brand-50 text-brand-700"
                  : "border-line bg-surface-muted text-ink-faint"
            }`}
          >
            {xong ? (
              <Check className="size-4" strokeWidth={3} />
            ) : dang ? (
              <Phone className="size-3.5" />
            ) : (
              <CircleDashed className="size-3.5" />
            )}
          </span>
          {!cuoi && (
            <span
              className={`w-0.5 flex-1 ${xong ? "bg-success" : "bg-line"}`}
              style={{ minHeight: 16 }}
            />
          )}
        </div>

        <div className={`min-w-0 flex-1 ${cuoi ? "pb-1" : "pb-3.5"}`}>
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`text-sm ${
                xong
                  ? "font-medium text-ink"
                  : dang
                    ? "font-semibold text-brand-700"
                    : "text-ink-soft"
              }`}
            >
              {tt.ten}
            </span>

            {dang && !xong && (
              <span className="rounded-full bg-brand-100 px-2 py-0.5 text-[10px] font-bold text-brand-800">
                đang ở đây
              </span>
            )}
            {tt.tuChon && !dang && !xong && (
              <span
                className="rounded-full bg-surface-sunken px-1.5 py-0.5 text-[10px] font-medium text-ink-muted"
                title="Hệ thống không có dữ liệu để tự biết — CSKH chọn khi biết."
              >
                tự chọn
              </span>
            )}

            <button
              type="button"
              onClick={() => onLamViec(tt.ma)}
              aria-pressed={chon}
              className={
                chon
                  ? "rounded-full bg-brand-700 px-2.5 py-0.5 text-[11px] font-semibold text-white"
                  : xong
                    ? "rounded-full border border-line px-2.5 py-0.5 text-[11px] font-medium text-ink-soft hover:bg-surface-muted"
                    : dang
                      ? "rounded-full bg-brand-600 px-2.5 py-0.5 text-[11px] font-semibold text-white hover:bg-brand-700"
                      : "rounded-full border border-brand-300 px-2.5 py-0.5 text-[11px] font-medium text-brand-700 hover:bg-brand-50"
              }
            >
              {chon ? "Đang làm" : xong ? "Làm lại" : "Làm bước này"}
            </button>
          </div>

          {/* Việc phải làm — phần sau mũi tên trong đặc tả. */}
          <p className="mt-0.5 text-[11px] leading-snug text-ink-muted">
            {tt.viec}
          </p>

          {lan && (
            <p className="mt-1 text-[11px] leading-snug text-ink-soft">
              <span className="font-mono text-ink-muted">
                {gio(lan.xay_ra_luc)}
              </span>
              {lan.ket_qua && ` · ${NHAN_KET_QUA[lan.ket_qua] ?? lan.ket_qua}`}
              {lan.nhan_vien && ` · ${lan.nhan_vien}`}
              {lan.noi_dung && (
                <span className="block italic text-ink-muted">
                  “{lan.noi_dung}”
                </span>
              )}
            </p>
          )}
        </div>
      </li>
    );
  }

  return (
    <div className="min-w-0 space-y-3">
      <section
        aria-label={`Trạng thái khách hàng — ${tenKhach}`}
        className="min-w-0 overflow-hidden rounded-2xl border border-line bg-surface shadow-card"
      >
        {/* TIÊU ĐỀ MỘT DÒNG. Dòng phụ "Bấm vào bước để làm…" đã bỏ theo yêu cầu
            09/08 — nó mô tả mô hình chuỗi bước không còn nữa. */}
        <div className="border-b border-line px-4 py-3">
          <h2 className="text-sm font-semibold text-ink">
            Trạng thái khách hàng — {tenKhach}
          </h2>
        </div>

        <div className="space-y-3 px-4 py-3">
          <div>
            <span className="text-[11px] font-bold uppercase tracking-wide text-ink-faint">
              Trước khám
            </span>
            <ol className="mt-1.5">
              {TRUOC_KHAM.map((tt, i) => (
                <Node key={tt.ma} tt={tt} cuoi={i === TRUOC_KHAM.length - 1} />
              ))}
            </ol>
          </div>

          <div>
            <span className="text-[11px] font-bold uppercase tracking-wide text-ink-faint">
              Sau khám
            </span>
            <ol className="mt-1.5">
              {SAU_KHAM.map((tt, i) => (
                <Node key={tt.ma} tt={tt} cuoi={i === SAU_KHAM.length - 1} />
              ))}
            </ol>
          </div>

          {/* MỐC TẠI QUẦY — một chạm, và chúng đổi trạng thái THẬT của lịch hẹn
              (check-in mở lượt khám vào hàng đợi tiếp nhận, check-out đóng
              trạng thái khám). Không phải cờ riêng chỉ màn này thấy. */}
          <div className="space-y-1.5 border-t border-line pt-3">
            <span className="text-[11px] font-bold uppercase tracking-wide text-ink-faint">
              Mốc tại quầy
            </span>
            <div className="flex flex-wrap gap-1.5">
              {MOC_QUAY.map((m) => {
                const daGhi = cacLan(m.ma).length > 0;
                const thieuLich =
                  !lich.id && (m.ma === "CHECK_IN" || m.ma === "CHECK_OUT");
                return (
                  <button
                    key={m.ma}
                    type="button"
                    onClick={() => void ghiMoc(m.ma)}
                    disabled={daGhi || dangGhiMoc !== null || thieuLich}
                    title={thieuLich ? "Khách chưa có lịch hẹn nào" : undefined}
                    className={`rounded-xl border px-2.5 py-1.5 text-[11px] font-semibold transition-colors disabled:opacity-60 ${
                      daGhi
                        ? "border-success/40 bg-success-bg text-success"
                        : "border-brand-300 text-brand-700 hover:bg-brand-50"
                    }`}
                  >
                    {daGhi ? "✓ " : ""}
                    {dangGhiMoc === m.ma ? "Đang ghi…" : m.ten}
                  </button>
                );
              })}
            </div>
            {loiMoc && <p className="text-[11px] text-danger">{loiMoc.loi}</p>}
          </div>
        </div>

        {/* KẾT QUẢ SIÊU ÂM / XÉT NGHIỆM — ảnh, video và phiếu. Đặc tả ghi rõ
            "cần gửi được cả video cho bệnh nhân". */}
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
