"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  ChevronDown,
  ExternalLink,
  Search,
  UsersRound,
  X,
} from "lucide-react";
import { useMemo, useState, useTransition,
  useCallback,
} from "react";

import StatCard, { StatRow } from "@/components/ui/StatCard";
import StatusChip, { type StatusTone } from "@/components/ui/StatusChip";
import { fmtDate, fmtDateTimeOrDate, conToi, mocMs, nowMs } from "@/lib/datetime";
import { unaccentVi } from "@/lib/validation";
import { nhanLyDoHuy } from "@/lib/ly-do-huy";
import PatientAdminEditor from "../PatientAdminEditor";
import BaoXepBacSi from "./BaoXepBacSi";
// Khối "Ghi một tương tác khác" đã bỏ 09/08/2026 (mỗi trạng thái có bộ nút
// riêng rồi), và `GhiTuongTac.tsx` xoá hẳn theo.
import { tieuDeHanhDong, coBoNut } from "./HanhDongTrangThai";
import type { DongLichSu } from "./so-tuong-tac";
import HanhDongTrangThai from "./HanhDongTrangThai";
import VungLamViecKhach, { type MocLich } from "./VungLamViecKhach";
import LichTrungCuaKhach from "./LichTrungCuaKhach";
import DatLichModal from "./DatLichModal";
import LichSuCacLanKham from "./LichSuCacLanKham";
import PhanHoiKhach, { type DongPhanHoi } from "./PhanHoiKhach";
// `NhacTaiKham` không còn được dựng ở màn này (Quang chốt 09/08/2026). File
// component vẫn nằm nguyên trong thư mục — chưa xoá, vì nó là cả một khối chức
// năng chứ không phải vài dòng trang trí.
import type { TepKetQuaRow } from "./TepKetQua";

/** Một dòng của view `v_trang_thai_cskh` — việc gấp nhất đang mở của một khách. */
export interface TrangThaiCskh {
  clinic_patient_id: string;
  trang_thai: string;
  /** Nhãn hiển thị, lấy từ bảng `luat_cskh` — phòng khám đổi chữ được. */
  nhan: string;
  han_xu_ly: string | null;
  /** Việc ĐẠI DIỆN có quá hạn không. */
  qua_han: boolean;
  /** Tổng số việc đang mở của khách này — màn nói được "còn N việc khác". */
  so_viec_mo: number;
  /** Có BẤT KỲ việc nào quá hạn không, kể cả việc không được chọn làm đại diện. */
  co_viec_qua_han: boolean;
  appointment_id: string | null;
  da_xac_nhan: boolean;
}

// Màu theo mức gấp, KHÔNG theo thứ tự bảng chữ cái. Đỏ dành cho việc mà chậm
// một ngày là khách đi về tay không.
const TONE_VIEC: Record<string, StatusTone> = {
  // DA_CHECKIN là mã ưu tiên 0 của view (migration 20260810000004) và là mã
  // được thêm SAU khi hai bảng này ra đời — nên tới 10/08/2026 cả hai vẫn thiếu
  // nó, và khách đang đứng ở phòng khám rơi vào nhánh `?? "ready"` cùng một câu
  // "bước tiếp" mượn từ nhãn của view. Không nổ lỗi, chỉ nói sai.
  DA_CHECKIN: "in_progress",
  CHO_BAC_SI: "in_progress",
  KQ_CHUA_GUI: "assigned",
  CHO_KQ_XN: "ready",
  GOI_LAI: "assigned",
  HOI_LY_DO_HUY: "ready",
  HEN_GOI_LAI: "ready",
  NHAC_DI_KHAM: "assigned",
  NHAC_HEN_MAI: "assigned",
  MOI_TAI_KHAM: "ready",
  CHO_XAC_NHAN: "ready",
};

// Việc phải làm, viết ở thể mệnh lệnh. Nhãn trạng thái nói KHÁCH đang ở đâu;
// cột này nói NGƯỜI TRỰC phải nhấc máy lên làm gì.
const BUOC_TIEP: Record<string, string> = {
  DA_CHECKIN: "Khách đã tới — xem tình trạng sau khám",
  CHO_BAC_SI: "Nhắc bác sĩ duyệt kết quả",
  KQ_CHUA_GUI: "Gọi trả kết quả cho khách",
  CHO_KQ_XN: "Hỏi đơn vị xét nghiệm",
  GOI_LAI: "Gọi lại (lần trước chưa gặp)",
  HOI_LY_DO_HUY: "Gọi hỏi vì sao huỷ",
  HEN_GOI_LAI: "Đã hẹn gọi lại hôm nay",
  NHAC_DI_KHAM: "Gọi nhắc đi khám",
  NHAC_HEN_MAI: "Gọi nhắc hẹn ngày mai",
  MOI_TAI_KHAM: "Gọi mời tái khám",
  CHO_XAC_NHAN: "Gọi xác nhận lịch",
};

const NHAN_LOAI_NGAN: Record<string, string> = {
  XAC_NHAN_LICH: "Xác nhận lịch",
  NHAC_HEN: "Nhắc hẹn",
  CHECK_XN: "Hỏi đơn vị XN",
  TRA_KQ: "Trả kết quả",
  HOI_LY_DO_HUY: "Hỏi lý do huỷ",
  HOI_THAM: "Hỏi thăm",
  KHAC: "Việc khác",
  CHECK_IN: "Check-in",
  CHECK_OUT: "Check-out",
  THANH_TOAN: "Thanh toán",
  MUA_THUOC: "Mua thuốc",
};
const NHAN_KQ_NGAN: Record<string, string> = {
  DA_LIEN_HE: "đã liên hệ",
  CHUA_NGHE_MAY: "không nghe máy",
  KHONG_LIEN_LAC_DUOC: "không liên lạc được",
  HEN_GOI_LAI: "khách hẹn gọi lại",
  CAN_BAC_SI: "cần hỏi bác sĩ",
  TU_CHOI: "từ chối",
  BO_QUA: "bỏ qua",
  GHI_NHAN: "đã ghi nhận",
};

/** Hôm nay theo giờ Việt Nam, dạng yyyy-mm-dd — cùng dạng `han_xu_ly` của view.
 *
 *  So chuỗi chứ không so `Date`: `han_xu_ly` là một NGÀY (không giờ), và dựng
 *  `new Date("2026-08-08")` ra nửa đêm UTC — tức 07:00 sáng ở Việt Nam. Mọi
 *  việc đến hạn hôm nay sẽ bị coi là chưa tới hạn cho tới 7 giờ sáng. */
function homNayVn(): string {
  return new Date(Date.now() + 7 * 3600 * 1000).toISOString().slice(0, 10);
}

/** Một dòng cho ô "Tương tác gần nhất". `undefined` = chưa có lần nào. */
function tomTatTuongTac(ds: DongLichSu[] | undefined): string | undefined {
  const d = ds?.[0];
  if (!d) return undefined;
  const ngay = new Date(d.xay_ra_luc).toLocaleDateString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  });
  const kq = d.ket_qua ? ` · ${NHAN_KQ_NGAN[d.ket_qua] ?? d.ket_qua}` : "";
  return `${ngay} · ${NHAN_LOAI_NGAN[d.loai] ?? d.loai}${kq}`;
}
import AppointmentEditModal, { type EditableAppt } from "./AppointmentEditModal";

export interface CustomerRow {
  clinic_patient_id: string;
  patient_code: string;
  full_name: string;
  date_of_birth: string | null;
  birth_year: number | null;
  phone_primary: string | null;
  phone_secondary: string | null;
  gender: string | null;
  ethnicity: string | null;
  nationality: string | null;
  occupation: string | null;
  patient_objection: string | null;
  address: string | null;
  guardian_name: string | null;
  location_id: string | null;
  created_at: string | null;
  van_de_di_kham: string | null;
  linh_vuc: string | null;
}

/** Một dòng trong bảng "khách này đang có mấy lịch". Đủ để nhận ra lịch nào là
 *  lịch nào rồi quyết bỏ cái nào — không hơn. */
export interface LichSapToi {
  id: string;
  slot_start: string;
  status: string;
  service_name: string | null;
  doctor_name: string | null;
}

/** Một BƯỚC CSKH đã bấm bên trong một lượt khám. */
export interface BuocCham {
  luc: string;
  trang_thai_ma: string | null;
  loai: string;
  ket_qua: string | null;
  nhan_vien: string | null;
}

/** Một LƯỢT KHÁM: lịch hẹn + mốc thời gian thật + các bước chăm sóc của nó. */
export interface LuotKham {
  id: string;
  slot_start: string;
  status: string;
  /** Mã dịch vụ — nút "Tái khám" khoá theo nó, không khoá theo tên. */
  service_type_id: string | null;
  service_name: string | null;
  doctor_name: string | null;
  /** Lượt trước trong chuỗi tái khám. null = mở đầu một đợt. */
  lich_truoc_id: string | null;
  /** Lý do huỷ CỦA CHÍNH LƯỢT NÀY — mã chọn sẵn và chữ tự viết. */
  ly_do_huy_ma: string | null;
  cancellation_reason: string | null;
  created_at: string | null;
  cancelled_at: string | null;
  /** `visit.checked_in_at`. null = khách chưa từng check-in lượt này. */
  bat_dau: string | null;
  /** `visit.closed_at` → `finalized_at` → dòng CHECK_OUT của CSKH. null = chưa
   *  đóng, và nói ra như thế đúng hơn là bịa một giờ. */
  ket_thuc: string | null;
  buoc: BuocCham[];
}

/** Một ĐỢT: các lượt nối nhau bằng `lich_truoc_id`, sớm trước. */
export interface ChuoiKham {
  luot: LuotKham[];
}

/** MỘT việc CSKH đang mở — một dòng của `v_viec_cskh` (20260810000008).
 *
 *  Khác `TrangThaiCskh` ở đúng một điểm, và đó là điểm quan trọng: view kia thu
 *  về MỘT dòng cho MỘT KHÁCH, còn view này giữ nguyên mọi việc. Cột giữa và cột
 *  phải làm việc trên MỘT LƯỢT, nên chúng cần biết việc nào thuộc lượt nào —
 *  `appointment_id` NULL = việc của khách, đúng với mọi lượt. */
export interface ViecCskh {
  clinic_patient_id: string;
  trang_thai: string;
  nhan: string;
  uu_tien: number;
  han_xu_ly: string | null;
  qua_han: boolean;
  appointment_id: string | null;
}

/** Một lời hẹn CSKH tự đặt cho mình, CHƯA ĐÓNG.
 *
 *  `gio_goi` null = chỉ hẹn tới ngày, KHÔNG phải 00:00 (migration
 *  20260810000006). Khác biệt ấy phải giữ tới tận màn hình: in "00:00" cho một
 *  lời hẹn không có giờ là bịa ra một mốc mà người trực sẽ tin. */
export interface HenGoiLai {
  id: string;
  ngay_goi: string;
  gio_goi: string | null;
  ly_do: string;
  tao_boi: string | null;
  created_at: string | null;
}

/** Trạng thái mà một lượt khám còn đang diễn ra — chưa đóng, chưa chết.
 *
 *  Cùng tập hợp với `CHUA_DONG` ở `page.tsx`; hai chỗ vì một chạy ở server một
 *  chạy ở trình duyệt, nhưng phải đọc cùng một danh sách. Đổi ở đây thì đổi cả
 *  ở kia. */
const LUOT_CHUA_DONG = [
  "SCHEDULED",
  "CSKH_CONFIRMED",
  "CONFIRMED",
  "CHECKED_IN",
];

/** LƯỢT NÀO ĐANG ĐƯỢC LÀM VIỆC, khi người dùng chưa tự chọn.
 *
 *  Viết ĐÚNG MỘT CHỖ, và viết đúng luật người trực cần — không phải luật "lịch
 *  sắp tới" của danh sách bên trái:
 *
 *    1. Khách đang có mặt ở phòng khám thì đó là lượt duy nhất đáng quan tâm.
 *    2. Không thì tới lượt sắp diễn ra gần nhất — việc phải chuẩn bị.
 *    3. Không nữa thì lượt chưa đóng mới nhất — việc còn dở.
 *    4. Cuối cùng mới tới lượt mới nhất, kể cả đã xong: xem lại chuyện vừa rồi.
 *
 *  Nhánh 2 CHỈ nhận lượt chưa đóng. Đây là lỗi Quang gặp: một lượt checkout
 *  lúc 12:25 nhưng giờ hẹn 18:15 vẫn "còn tới", nên nó chiếm chỗ của lượt tái
 *  khám vừa đặt và màn hình không bao giờ chuyển. */
/** Khách chưa có lịch hẹn nào. Khai một lần để React không dựng vật mới mỗi
 *  lần vẽ (prop đổi tham chiếu là con của nó vẽ lại vô cớ). */
const EMPTY_LUOT: MocLich = {
  id: null,
  status: null,
  slot_start: null,
  created_at: null,
  cancelled_at: null,
  ly_do_huy_ma: null,
  cancellation_reason: null,
  service_type_id: null,
  service_name: null,
};

/** NHÃN DANH SÁCH NÓI ĐÚNG CHUYỆN VỪA XẢY RA, không chỉ nói loại việc.
 *
 *  QUANG 10/08/2026: *"trạng thái khi nhắn chưa nghe máy hay hẹn gọi lại sau
 *  chưa được đồng bộ ngay trên khu danh sách khách hàng"*.
 *
 *  View ĐANG đồng bộ — nhưng nó gộp. Nhánh `GOI_LAI` của `v_trang_thai_cskh`
 *  (`20260810000004:103-113`) nhận CẢ BA kết quả `CHUA_NGHE_MAY`,
 *  `KHONG_LIEN_LAC_DUOC`, `HEN_GOI_LAI` và trả về đúng một nhãn "Cần gọi lại".
 *  Nên bấm "Không nghe máy" hay bấm "Hẹn gọi lại sau", cột giữa đổi mà chip bên
 *  trái đứng yên — người trực đọc thành "chưa ghi được".
 *
 *  Ba chuyện ấy dẫn tới ba việc khác nhau: không nghe máy thì gọi lại ngay,
 *  không liên lạc được thì tìm số khác, khách hẹn gọi lại thì ĐỪNG gọi bây giờ.
 *  Gộp làm một là bỏ đi thứ duy nhất người trực cần biết trước khi bấm số.
 *
 *  KHÔNG sửa view: nhãn `luat_cskh` là thứ phòng khám đổi được không cần
 *  deploy, và `so_viec_mo`/`qua_han` vẫn phải đếm theo LOẠI việc. Đây là lớp
 *  hiển thị nói thêm điều view cố ý không đủ mịn để nói — cùng cách `quá giờ
 *  hẹn` đang làm ngay bên dưới. */
function nhanChiTiet(
  tt: TrangThaiCskh,
  lichSu: DongLichSu[] | undefined,
): string {
  if (tt.trang_thai !== "GOI_LAI") return tt.nhan;
  // `lichSu` xếp mới nhất trước (xem truy vấn ở `page.tsx`), và nhánh GOI_LAI
  // của view cũng đọc lần chạm CUỐI — nên hai bên nhìn cùng một dòng.
  const kq = lichSu?.[0]?.ket_qua;
  const noi = kq ? NHAN_KET_QUA_NGAN_GOI[kq] : undefined;
  return noi ? `${tt.nhan} · ${noi}` : tt.nhan;
}

/** Ba lối ra của một cuộc gọi không gặp — viết đủ chữ, không viết tắt. */
const NHAN_KET_QUA_NGAN_GOI: Record<string, string> = {
  CHUA_NGHE_MAY: "không nghe máy",
  KHONG_LIEN_LAC_DUOC: "không liên lạc được",
  HEN_GOI_LAI: "khách hẹn gọi lại",
};

/** Gọi tên lượt đang xem cho đúng chuyện của nó.
 *
 *  "Lịch hẹn sắp tới" cho một lượt đã khám xong là câu nói sai mà người trực
 *  đọc cho khách nghe. */
function nhanLuot(l: MocLich | null): string {
  if (!l?.status) return "Lịch hẹn";
  if (l.status === "CHECKED_IN") return "Lượt đang khám";
  if (l.status === "COMPLETED") return "Lượt đã khám xong";
  if (["CANCELLED", "NO_SHOW", "DOCTOR_DECLINED"].includes(l.status))
    return "Lượt đã đóng";
  return conToi(l.slot_start, nowMs()) ? "Lịch hẹn sắp tới" : "Lịch hẹn";
}

function luotMacDinh(cac: LuotKham[]): LuotKham | undefined {
  if (!cac.length) return undefined;
  const bayGio = nowMs();
  const dangKham = cac.find((l) => l.status === "CHECKED_IN");
  if (dangKham) return dangKham;
  const sapToi = cac.find(
    (l) => LUOT_CHUA_DONG.includes(l.status) && conToi(l.slot_start, bayGio),
  );
  if (sapToi) return sapToi;
  const conDo = [...cac]
    .reverse()
    .find((l) => LUOT_CHUA_DONG.includes(l.status));
  return conDo ?? cac[cac.length - 1];
}

export interface ApptInfo {
  /** `appointment.id` của LỊCH ĐẠI DIỆN. Đây là định danh lượt, và nó KHÁC
   *  `appt?.id` — `appt` chỉ có khi lượt còn đổi/huỷ được. Xem ghi chú ở
   *  `page.tsx` chỗ dựng `apptByPatient`. */
  id: string | null;
  slot_start: string;
  status: string;
  upcoming: boolean;
  /** Lịch đại diện đã qua giờ mà khách vẫn chưa đến. */
  qua_gio_hen?: boolean;
  count: number;
  /** MỌI lịch còn sống và còn sắp tới của khách này, sớm trước.
   *
   *  `slot_start` một mình chỉ kể được LỊCH ĐẠI DIỆN, nên khách đặt ba lần
   *  trông y hệt khách đặt một lần — màn chỉ nói "+N việc", một con số đếm VIỆC
   *  chứ không đếm lịch, và không bấm được vào đâu để xem. Đây là danh sách để
   *  cảnh báo trùng và để bỏ bớt. */
  sapToi: LichSapToi[];
  /** Lượt khám gần nhất ĐÃ XONG — nguồn cho nút "Tái khám" (giữ nguyên dịch
   *  vụ) và cho mắt xích `lich_truoc_id`. null = khách chưa khám lần nào. */
  lanKhamGanNhat: {
    id: string;
    slot_start: string;
    service_type_id: string | null;
    service_name: string | null;
  } | null;
  /** Số lượt ĐÃ KHÁM XONG. Đặt rồi huỷ không tính. */
  soLanKham: number;
  /** Lịch đại diện có nối vào một lượt khám trước không (`lich_truoc_id`). */
  laTaiKham: boolean;
  examined: boolean;
  /** Mốc hệ thống cho vùng làm việc: lịch được tạo lúc nào, huỷ lúc nào. */
  created_at?: string | null;
  cancelled_at?: string | null;
  /** Lý do huỷ của lịch đại diện — mã chọn sẵn, và chữ CSKH tự viết. */
  ly_do_huy_ma?: string | null;
  cancellation_reason?: string | null;
  appt?: EditableAppt;
}

export interface Opt {
  id: string;
  label: string;
}

export type Period = "today" | "week" | "month" | "all";
export type ByDim = "created" | "appt";

type CustomerTab =
  | "all"
  | "upcoming"
  | "examined"
  | "qua_sla"
  | "cho_xac_nhan";

const PERIODS: { key: Period; label: string }[] = [
  { key: "today", label: "Hôm nay" },
  { key: "week", label: "Tuần này" },
  { key: "month", label: "Tháng này" },
  { key: "all", label: "Tất cả" },
];

// LỌC BẰNG CHÍNH BỐN Ô SỐ Ở TRÊN — không có hàng tab riêng nữa.
//
// Trước đây màn này có cả hai, và bốn nhãn tab KHÔNG khớp bốn con số: tab ghi
// "Quá SLA" nhưng lọc `without_appointment` (khách chưa có lịch hẹn), tab
// "Nhiệm vụ hôm nay" lại lọc `examined`. Bấm vào một tab rồi so với con số ở
// trên là ra hai kết quả khác nhau, và không có gì trên màn hình nói vì sao.
//
// Nay mỗi ô số VÀ phép lọc của nó dùng CHUNG một vị từ (`hopVoiTab`), nên bấm ô
// đang hiện 29 thì thấy đúng 29 dòng ấy. Không còn tab "Tất cả khách hàng":
// mặc định đã là tất cả, và bỏ lọc bằng cách bấm lại ô đang chọn.

/** "Bộ lọc" — MỘT nút, mở ra mọi thứ thu hẹp được danh sách.
 *
 *  Gộp hai điều khiển trước đây đứng rời nhau ở hai đầu màn hình: ô chọn
 *  "lọc theo ngày tạo / ngày hẹn" và bốn nút kỳ (Hôm nay → Tất cả). Chúng luôn
 *  đọc cùng nhau — "tuần này" một mình không có nghĩa, phải biết tuần này
 *  THEO ngày tạo hay theo ngày hẹn — nên tách chúng ra hai đầu là bắt người
 *  dùng ghép lại bằng mắt.
 */
function BoLoc({
  period,
  by,
  onChon,
}: {
  period: Period;
  by: ByDim;
  onChon: (period: Period, by: ByDim) => void;
}) {
  const [mo, setMo] = useState(false);
  const dangLoc = period !== "all";
  const nhanKy = PERIODS.find((p) => p.key === period)?.label ?? "Tất cả";

  return (
    <div className="relative">
      {/* CHỈ CÒN MŨI TÊN, nằm sát mép phải ô tìm kiếm (Quang chốt 09/08/2026).
          Chữ "Bộ lọc" chiếm chỗ cho một thứ chỉ thỉnh thoảng mới mở.
          NHƯNG khi ĐANG lọc thì vẫn phải nói ra: một mũi tên trông y hệt lúc
          lọc và lúc không là cách để người dùng nhìn một danh sách đã bị cắt mà
          tưởng đó là tất cả. Nên lúc ấy mũi tên đổi màu và có chấm báo. */}
      <button
        type="button"
        onClick={() => setMo((v) => !v)}
        aria-expanded={mo}
        aria-label={dangLoc ? `Bộ lọc — đang lọc ${nhanKy}` : "Bộ lọc"}
        title={
          dangLoc
            ? `Đang lọc: ${nhanKy}${by === "appt" ? " · theo ngày hẹn" : ""}`
            : "Bộ lọc"
        }
        className={`relative grid size-8 place-items-center rounded-lg transition-colors ${
          dangLoc
            ? "bg-brand-50 text-brand-700"
            : "text-ink-muted hover:bg-surface-muted hover:text-ink"
        }`}
      >
        <ChevronDown
          className={`size-4 transition-transform ${mo ? "rotate-180" : ""}`}
          aria-hidden="true"
        />
        {dangLoc && (
          <span className="absolute right-1 top-1 size-1.5 rounded-full bg-brand-600" />
        )}
      </button>

      {mo && (
        <>
          {/* Bấm ra ngoài là đóng. Thiếu lớp này thì bảng lọc chỉ đóng khi bấm
              đúng cái nút đã mở nó. */}
          <button
            type="button"
            aria-label="Đóng bộ lọc"
            onClick={() => setMo(false)}
            className="fixed inset-0 z-40 cursor-default"
          />
          <div className="absolute right-0 top-full z-50 mt-2 w-64 space-y-3 rounded-2xl border border-line bg-surface p-3 shadow-lg">
            <div className="space-y-1.5">
              <span className="block text-[11px] font-semibold uppercase tracking-wide text-ink-faint">
                Khoảng thời gian
              </span>
              <div className="grid grid-cols-2 gap-1" role="group">
                {PERIODS.map((entry) => (
                  <button
                    key={entry.key}
                    type="button"
                    onClick={() => onChon(entry.key, by)}
                    className={`rounded-lg px-2.5 py-1.5 text-xs font-medium transition-all ${
                      entry.key === period
                        ? "bg-brand-600 font-bold text-white"
                        : "bg-surface-sunken text-ink-muted hover:text-ink"
                    }`}
                  >
                    {entry.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-1.5 border-t border-line pt-2.5">
              <span className="block text-[11px] font-semibold uppercase tracking-wide text-ink-faint">
                Tính theo
              </span>
              <div className="grid grid-cols-2 gap-1" role="group">
                {(
                  [
                    ["created", "Ngày tạo"],
                    ["appt", "Ngày hẹn"],
                  ] as [ByDim, string][]
                ).map(([ma, nhan]) => (
                  <button
                    key={ma}
                    type="button"
                    onClick={() => onChon(period, ma)}
                    className={`rounded-lg px-2.5 py-1.5 text-xs font-medium transition-all ${
                      by === ma
                        ? "bg-brand-600 font-bold text-white"
                        : "bg-surface-sunken text-ink-muted hover:text-ink"
                    }`}
                  >
                    {nhan}
                  </button>
                ))}
              </div>
            </div>

            {dangLoc && (
              <button
                type="button"
                onClick={() => onChon("all", by)}
                className="w-full rounded-lg border border-line py-1.5 text-xs font-semibold text-ink-soft hover:bg-surface-muted"
              >
                Bỏ lọc thời gian
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function initials(name: string): string {
  return (
    name
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .slice(-2)
      .map((word) => word[0]?.toLocaleUpperCase("vi-VN") ?? "")
      .join("") || "KH"
  );
}

function appointmentStatus(status: string): { label: string; tone: StatusTone } {
  const known: Record<string, { label: string; tone: StatusTone }> = {
    SCHEDULED: { label: "Chờ xác nhận (lịch cũ)", tone: "ready" },
    CSKH_CONFIRMED: { label: "Chờ bác sĩ (lịch cũ)", tone: "assigned" },
    CONFIRMED: { label: "Đã đặt lịch", tone: "assigned" },
    CHECKED_IN: { label: "Đã check-in", tone: "in_progress" },
    COMPLETED: { label: "Đã khám xong", tone: "completed" },
    CANCELLED: { label: "Đã hủy", tone: "cancelled" },
    NO_SHOW: { label: "Không đến", tone: "cancelled" },
    DOCTOR_DECLINED: { label: "Bác sĩ từ chối", tone: "cancelled" },
  };
  return known[status] ?? { label: status, tone: "ready" };
}

function CustomerTableHeader() {
  return (
    <div className="grid grid-cols-[minmax(180px,1.2fr)_minmax(100px,0.7fr)_minmax(180px,1.2fr)_minmax(180px,1.2fr)_minmax(100px,0.7fr)_minmax(90px,0.6fr)_32px] gap-3 border-b border-line bg-surface-muted px-4 py-2 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">
      <span>Khách hàng</span>
      <span>Trạng thái</span>
      <span>Tương tác gần nhất</span>
      <span>Bước tiếp theo</span>
      <span>Hạn xử lý</span>
      <span>Người xử lý gần nhất</span>
      <span aria-hidden="true" />
    </div>
  );
}

export default function CustomersView({
  rows,
  apptByPatient,
  cskhByPatient,
  tuongTacByPatient,
  trangThaiByPatient,
  viecMoByPatient,
  phanHoiByPatient,
  lichSuKhamByPatient,
  henGoiLaiByPatient,
  tepByPatient,
  locations,
  q,
  period,
  by,
  initialSelected,
  initialViec = null,
  initialLuot = null,
  canEdit = false,
  canManage = false,
  services = [],
  doctors = [],
}: {
  rows: CustomerRow[];
  apptByPatient: Record<string, ApptInfo>;
  cskhByPatient: Record<
    string,
    {
      status: string;
      lastInteraction: string | null;
      nextStep: string | null;
      deadline: string | null;
      assignee: string | null;
    }
  >;
  tuongTacByPatient: Record<string, DongLichSu[]>;
  trangThaiByPatient: Record<string, TrangThaiCskh>;
  /** MỌI việc đang mở theo khách — để cột giữa/phải bám đúng LƯỢT. */
  viecMoByPatient: Record<string, ViecCskh[]>;
  phanHoiByPatient: Record<string, DongPhanHoi[]>;
  /** Lịch sử khám theo khách, đã ghép sẵn thành từng đợt ở server. */
  lichSuKhamByPatient: Record<string, ChuoiKham[]>;
  /** Lời hẹn gọi lại CHƯA ĐÓNG, theo khách. */
  henGoiLaiByPatient: Record<string, HenGoiLai[]>;
  tepByPatient: Record<string, TepKetQuaRow[]>;
  /** Mốc gọi nhắc tái khám đang mở, theo khách. Rỗng = không có việc nào. */
  locations: Opt[];
  q: string;
  period: Period;
  by: ByDim;
  initialSelected: string | null;
  /** Trạng thái CSKH mở sẵn ở cột phải (`?viec=`). Chuông thông báo đặt nó. */
  initialViec?: string | null;
  /** Lượt khám mở sẵn (`?luot=` — `appointment.id`). */
  initialLuot?: string | null;
  canEdit?: boolean;
  canManage?: boolean;
  services?: Opt[];
  doctors?: Opt[];
}) {
  const router = useRouter();
  const [tab, setTab] = useState<CustomerTab>("all");
  /** Khách đang mở bảng "mấy lịch trùng" (clinic_patient_id), null = đang đóng. */
  const [xemTrung, setXemTrung] = useState<string | null>(null);

  /** Bấm một ô số = lọc theo ô đó. Bấm lại đúng ô đang chọn = bỏ lọc. */
  const chonLoc = (key: CustomerTab) =>
    setTab((cu) => (cu === key ? "all" : key));
  const [selectedId, setSelectedId] = useState<string | null>(initialSelected);
  const [term, setTerm] = useState(q);
  const [editOpen, setEditOpen] = useState(false);
  // TRẠNG THÁI CSKH vừa bấm ở cột giữa. Dùng làm `key` cho khối hành động, nên
  // bấm trạng thái khác là component mount lại với đúng bộ nút — không cần
  // effect đồng bộ (thứ trình biên dịch React chặn ở repo này).
  //
  // null = chưa chọn gì ⇒ khối hành động chạy theo việc gấp nhất mà
  // `v_trang_thai_cskh` suy ra.
  //
  // KHỞI TẠO TỪ URL. Chuông thông báo gửi kèm `?viec=` để mở đúng việc nó nói
  // tới, thay vì thả người trực xuống việc gấp nhất do view suy ra — hai thứ
  // thường khác nhau, và cái khác nhau ấy chính là "bấm để xử lý" mà không xử
  // lý được gì.
  const [viecDangGhi, setViecDangGhi] = useState<string | null>(
    coBoNut(initialViec) ? initialViec : null,
  );
  /** GHI CHÚ ĐANG GÕ — dùng chung cho CẢ HAI CỘT.
   *
   *  Ô gõ nằm ở cột phải, còn nút ghi của phần lớn trạng thái nay nằm ở cột
   *  giữa (`MOT_CHAM`). Để mỗi cột giữ một chuỗi riêng thì gõ xong bấm bên kia
   *  là ghi chú rơi mất, và không có gì nói cho người dùng biết là nó rơi.
   *
   *  Xoá khi đổi khách hoặc đổi lượt: ghi chú viết cho người này không được
   *  dính sang người sau. */
  const [ghiChuChung, setGhiChuChung] = useState("");
  /** Form đặt lịch đang mở kiểu nào; null = đóng. */
  const [datLich, setDatLich] = useState<"tai-kham" | "kham-moi" | null>(null);
  // LƯỢT KHÁM ĐANG XEM — cặp (khách, lượt), không phải mỗi id lượt.
  //
  // Đổi khách mà chỉ giữ id lượt thì lượt của người trước dính sang người sau.
  // So `pid` rồi bỏ qua là đủ; không cần effect đồng bộ (thứ trình biên dịch
  // React chặn ở repo này — xem ghi chú `viecDangGhi` bên trên).
  //
  // null = để `luotMacDinh` chọn. Có giá trị = người dùng đã bấm một lượt cụ
  // thể trong "Lịch sử các lần khám", hoặc vừa đặt xong một lịch mới.
  const [luotChon, setLuotChon] = useState<{ pid: string; id: string } | null>(
    initialLuot && initialSelected
      ? { pid: initialSelected, id: initialLuot }
      : null,
  );
  // actionLoading/actionMsg đi cùng hai nút "xác nhận khách sẽ tới" / "báo
  // không tới" đã bỏ — xem ghi chú ở khối nút bên dưới.
  const [isPending, startTransition] = useTransition();

  function go(nextPeriod: Period, nextQ: string, nextBy: ByDim) {
    const params = new URLSearchParams();
    if (nextQ.trim()) params.set("q", nextQ.trim());
    if (nextPeriod !== "all") params.set("period", nextPeriod);
    if (nextBy !== "created") params.set("by", nextBy);
    if (selectedId) params.set("selected", selectedId);
    // Lượt và việc đi theo đường dẫn, để F5 và một link gửi cho ca sau vẫn mở
    // đúng chỗ người trước đang đứng.
    if (selectedId && luotChon?.pid === selectedId)
      params.set("luot", luotChon.id);
    if (viecDangGhi) params.set("viec", viecDangGhi);
    const query = params.toString();
    startTransition(() => {
      router.push(`/customers${query ? `?${query}` : ""}`);
    });
  }

  const locName = (id: string | null) =>
    locations?.find((location) => location.id === id)?.label ?? "—";

  const searchedRows = useMemo(() => {
    const needle = unaccentVi(term.trim());
    if (!needle) return rows;
    return rows.filter((row) => {
      return [row.full_name, row.patient_code, row.phone_primary ?? ""]
        .map(unaccentVi)
        .some((value) => value.includes(needle));
    });
  }, [rows, term]);

  /** MỘT vị từ cho cả việc đếm ô số lẫn việc lọc danh sách.
   *
   * Đây là chỗ bản cũ sai: con số trên ô và phép lọc của tab được tính bằng hai
   * đoạn mã khác nhau, nên chúng nói hai điều khác nhau về cùng một tập khách.
   */
  // BỐN Ô SỐ ĐỌC CÙNG NGUỒN VỚI BẢNG BÊN DƯỚI.
  //
  // Đo trên bản thật 08/08: "Quá SLA" và "Chờ xác nhận" hiện 0 VĨNH VIỄN, dù
  // bảng ngay bên dưới đang có việc quá hạn. Vì hai ô ấy còn đọc nguồn cũ:
  //   · qua_sla     ← cskh_action.deadline_at — bảng 0 dòng, và hai câu INSERT
  //                   duy nhất ghi vào nó còn không có cột deadline_at.
  //   · cho_xac_nhan ← appointment.status === "SCHEDULED" — lịch mới vào thẳng
  //                    CONFIRMED (booking_service), nên không lịch nào ở đó.
  //
  // Một ô số luôn bằng 0 không đọc thành "chưa xây" — nó đọc thành "hôm nay
  // không có việc nào quá hạn". Và bấm vào thì ra danh sách rỗng trong khi
  // dòng ngay dưới đang đỏ. Đúng bệnh của tab "Ưu tiên" đã chữa hôm nay.
  const hopVoiTab = useCallback(
    (row: CustomerRow, key: CustomerTab): boolean => {
      if (key === "all") return true;
      const appointment = apptByPatient[row.clinic_patient_id];
      const tt = trangThaiByPatient[row.clinic_patient_id];
      // "Đã hoàn thành" vẫn theo LỊCH HẸN, không theo việc: khách khám xong là
      // một sự thật của buổi khám, không phải của hàng chờ CSKH.
      if (key === "examined") return Boolean(appointment?.examined);
      // ĐẾM THEO `co_viec_qua_han`, không theo việc đại diện. Một khách có thể
      // có ba việc mở mà chỉ một hiện ra; đếm việc hiện ra là đếm hụt, và một
      // ô số sai theo hướng thấp hơn sự thật là ô số không ai đi kiểm.
      if (key === "qua_sla") return Boolean(tt?.co_viec_qua_han);
      if (key === "cho_xac_nhan") return tt?.trang_thai === "CHO_XAC_NHAN";
      if (key === "upcoming") {
        // "Cần xử lý hôm nay" = có việc đang mở, tới hạn hôm nay hoặc đã quá.
        // Không đếm việc của tuần sau: ô này để biết sáng nay phải làm gì.
        if (!tt?.han_xu_ly) return false;
        return tt.han_xu_ly <= homNayVn();
      }
      return true;
    },
    [apptByPatient, trangThaiByPatient],
  );

  const visibleRows = useMemo(
    () => searchedRows.filter((row) => hopVoiTab(row, tab)),
    [searchedRows, tab, hopVoiTab],
  );

  const selected =
    selectedId === null
      ? null
      : (visibleRows.find((row) => row.clinic_patient_id === selectedId) ?? null);

  const selectedAppt = selected
    ? apptByPatient[selected.clinic_patient_id]
    : undefined;

  /** MỌI LƯỢT KHÁM của khách đang mở, phẳng ra và xếp sớm trước.
   *
   *  `lichSuKhamByPatient` đã gom sẵn thành từng ĐỢT ở server; ở đây chỉ cần
   *  danh sách phẳng để tra một lượt theo id. */
  const cacLuotCuaKhach = useMemo(() => {
    const pid = selected?.clinic_patient_id;
    if (!pid) return [] as LuotKham[];
    return (lichSuKhamByPatient[pid] ?? [])
      .flatMap((c) => c.luot)
      .sort((a, b) => mocMs(a.slot_start) - mocMs(b.slot_start));
  }, [lichSuKhamByPatient, selected]);

  /** LƯỢT ĐANG XEM — một giá trị, cho cả cột giữa lẫn cột phải.
   *
   *  ĐÂY LÀ THỨ TRƯỚC 10/08/2026 KHÔNG TỒN TẠI. Cột giữa đọc "lịch đại diện"
   *  do server đoán, và phép đoán ấy trả về MỘT lịch cho cả khách — nên khách
   *  có hai lượt (vừa khám xong + vừa đặt tái khám) thì màn hình đứng ở lượt
   *  cũ, mọi node xanh nguyên, và người trực không có cách nào chuyển sang lượt
   *  mới. Quang gọi đúng tên nó: *"vẫn ở lại màn hình làm việc của lượt khám
   *  trước đó"*.
   *
   *  Thứ tự: lượt người dùng CHỌN → luật mặc định → lịch đại diện của server.
   *  Nhánh cuối giữ cho những vai không nạp được `lichSuKhamByPatient`; bỏ nó
   *  là cột giữa trống trơn với Thu ngân, một lỗi tệ hơn lỗi đang chữa. */
  const luotDangXem: MocLich | null = useMemo(() => {
    const daChon =
      luotChon && luotChon.pid === selected?.clinic_patient_id
        ? cacLuotCuaKhach.find((l) => l.id === luotChon.id)
        : undefined;
    const luot = daChon ?? luotMacDinh(cacLuotCuaKhach);
    if (luot) {
      return {
        id: luot.id,
        status: luot.status,
        slot_start: luot.slot_start,
        created_at: luot.created_at,
        cancelled_at: luot.cancelled_at,
        ly_do_huy_ma: luot.ly_do_huy_ma,
        cancellation_reason: luot.cancellation_reason,
        service_type_id: luot.service_type_id,
        service_name: luot.service_name,
      };
    }
    if (!selectedAppt) return null;
    return {
      id: selectedAppt.id,
      status: selectedAppt.status,
      slot_start: selectedAppt.slot_start,
      created_at: selectedAppt.created_at ?? null,
      cancelled_at: selectedAppt.cancelled_at ?? null,
      ly_do_huy_ma: selectedAppt.ly_do_huy_ma ?? null,
      cancellation_reason: selectedAppt.cancellation_reason ?? null,
      service_type_id: selectedAppt.appt?.service_type_id ?? null,
      service_name: selectedAppt.appt?.service_name ?? null,
    };
  }, [luotChon, selected, cacLuotCuaKhach, selectedAppt]);

  /** VIỆC ĐANG MỞ THUỘC LƯỢT ĐANG XEM, gấp nhất trước.
   *
   *  `appointment_id` NULL = việc của KHÁCH chứ không của một lượt (kết quả xét
   *  nghiệm gắn `lab_result`, lời hẹn gọi lại gắn khách) — chúng đúng với mọi
   *  lượt nên luôn được giữ.
   *
   *  Thứ tự y hệt `v_trang_thai_cskh`: quá hạn trước, rồi ưu tiên, rồi hạn.
   *  Chép luật SẮP XẾP thì được — nó là ba phép so; chép luật SINH việc thì
   *  không, và đó là lý do `v_viec_cskh` tồn tại. */
  const viecCuaLuot = useMemo(() => {
    const pid = selected?.clinic_patient_id;
    if (!pid) return [] as ViecCskh[];
    const luotId = luotDangXem?.id ?? null;
    return (viecMoByPatient[pid] ?? [])
      .filter((v) => v.appointment_id === null || v.appointment_id === luotId)
      .sort(
        (a, b) =>
          Number(b.qua_han) - Number(a.qua_han) ||
          a.uu_tien - b.uu_tien ||
          (a.han_xu_ly ?? "").localeCompare(b.han_xu_ly ?? ""),
      );
  }, [viecMoByPatient, selected, luotDangXem]);

  /** Lượt đang xem có còn đổi / huỷ được không. `undefined` = không. */
  const apptSuaDuoc =
    selectedAppt?.appt && selectedAppt.appt.id === luotDangXem?.id
      ? selectedAppt.appt
      : undefined;

  /** Chọn một lượt để làm việc. Ghi vào URL luôn, để F5 không mất chỗ. */
  const chonLuot = useCallback(
    (id: string) => {
      const pid = selected?.clinic_patient_id;
      if (!pid) return;
      setLuotChon({ pid, id });
      // Đổi lượt là đổi ngữ cảnh: việc đang ghi dở thuộc lượt cũ, giữ lại là
      // ghi nhầm sổ. Về null để cột phải chạy theo việc gấp nhất của lượt mới.
      setViecDangGhi(null);
      setGhiChuChung("");
      const params = new URLSearchParams(window.location.search);
      params.set("selected", pid);
      params.set("luot", id);
      params.delete("viec");
      router.replace(`/customers?${params.toString()}`, { scroll: false });
    },
    [selected, router],
  );

  // Ba biến đếm cũ đã BỎ. Chúng tính bằng một đoạn mã riêng, tách khỏi phép
  // lọc của tab — và đó chính là chỗ con số trên ô và danh sách bên dưới nói
  // hai điều khác nhau. Nay cả hai đi qua `hopVoiTab`.

  // TRẠNG THÁI = VIỆC ĐANG MỞ, không phải "khách này đang ở đâu".
  //
  // View `v_trang_thai_cskh` trả về việc gấp nhất và nhãn của nó (nhãn lấy từ
  // bảng luat_cskh, nên phòng khám đổi chữ mà không cần deploy). Không có việc
  // nào thì nói thẳng "Không có việc" — thay cho "Đã đặt lịch", câu mà màn cũ
  // hiện cho gần như mọi khách và không nói CSKH phải làm gì tiếp.
  //
  // Hai nguồn cũ giữ lại làm đường lùi cho tới khi cskh_action được chốt thành
  // dữ liệu nhập khẩu chỉ đọc.
  function customerStatus(row: CustomerRow): { label: string; tone: StatusTone } {
    // QUÁ GIỜ HẸN LÀ ĐỎ, kể cả khi view nói chưa quá hạn.
    //
    // `v_trang_thai_cskh.qua_han` tính theo NGÀY (luat_cskh.so_ngay), nên một
    // lịch 08:15 hôm nay lúc 12:37 vẫn là "Nhắc đi khám hôm nay" màu xanh —
    // đúng theo ngày, sai theo việc phải làm. Đây là lớp hiển thị nên nó không
    // sửa view; nó chỉ nói thêm điều view không đủ mịn để nói.
    const quaGio = apptByPatient[row.clinic_patient_id]?.qua_gio_hen;
    const tt = trangThaiByPatient[row.clinic_patient_id];
    if (tt) {
      const nhan = nhanChiTiet(
        tt,
        tuongTacByPatient[row.clinic_patient_id],
      );
      return {
        label: quaGio ? `${nhan} · quá giờ hẹn` : nhan,
        tone: tt.qua_han || quaGio ? "overdue" : TONE_VIEC[tt.trang_thai] ?? "ready",
      };
    }
    const cskh = cskhByPatient[row.clinic_patient_id];
    const appt = apptByPatient[row.clinic_patient_id];
    if (cskh) {
      const statusMap: Record<string, { label: string; tone: StatusTone }> = {
        DONE: { label: "Hoàn thành", tone: "completed" },
        CLOSED: { label: "Hoàn thành", tone: "completed" },
        WAITING: { label: "Chờ phản hồi", tone: "ready" },
        IN_PROGRESS: { label: "Đang tư vấn", tone: "assigned" },
        OPEN: { label: "Đang xử lý", tone: "in_progress" },
      };
      return statusMap[cskh.status] ?? { label: cskh.status, tone: "ready" };
    }
    if (appt) {
      return appointmentStatus(appt.status);
    }
    return { label: "Khách mới", tone: "ready" };
  }

  /** Việc phải làm tiếp — chính là tên của trạng thái, viết ở thể mệnh lệnh. */
  function customerNextStep(row: CustomerRow): string | undefined {
    const tt = trangThaiByPatient[row.clinic_patient_id];
    return tt ? (BUOC_TIEP[tt.trang_thai] ?? tt.nhan) : undefined;
  }

  function customerDeadline(row: CustomerRow): { text: string; overdue: boolean } {
    const tt = trangThaiByPatient[row.clinic_patient_id];
    if (tt?.han_xu_ly) {
      // View đã tính `qua_han` theo giờ Việt Nam. Tính lại ở trình duyệt là
      // mời máy của người dùng — múi giờ nào cũng có — vào quyết định một câu
      // hỏi nghiệp vụ.
      return { text: fmtDate(tt.han_xu_ly), overdue: tt.qua_han };
    }
    const cskh = cskhByPatient[row.clinic_patient_id];
    if (!cskh?.deadline) return { text: "—", overdue: false };
    const now = new Date();
    const dl = new Date(cskh.deadline);
    const diffMin = Math.floor((dl.getTime() - now.getTime()) / 60000);
    if (diffMin < 0) {
      const overMin = -diffMin;
      if (overMin < 60) return { text: `Quá hạn ${overMin} phút`, overdue: true };
      const overHours = Math.floor(overMin / 60);
      if (overHours < 24) return { text: `Quá hạn ${overHours} giờ`, overdue: true };
      return { text: `Quá hạn ${Math.floor(overHours / 24)} ngày`, overdue: true };
    }
    if (diffMin < 60) return { text: `Còn ${diffMin} phút`, overdue: false };
    const hours = Math.floor(diffMin / 60);
    if (hours < 24) return { text: fmtDateTimeOrDate(cskh.deadline), overdue: false };
    return { text: fmtDate(cskh.deadline), overdue: false };
  }

  return (
    <div className="space-y-4">
      <StatRow>
        <StatCard
          label="Cần xử lý hôm nay"
          value={rows.filter((r) => hopVoiTab(r, "upcoming")).length}
          tone="brand"
          icon={<UsersRound className="size-5" />}
          onSelect={() => chonLoc("upcoming")}
          active={tab === "upcoming"}
        />
        <StatCard
          label="Quá SLA"
          value={rows.filter((r) => hopVoiTab(r, "qua_sla")).length}
          tone="danger"
          icon={<CalendarClock className="size-5 text-danger" />}
          onSelect={() => chonLoc("qua_sla")}
          active={tab === "qua_sla"}
        />
        <StatCard
          label="Chờ xác nhận"
          value={rows.filter((r) => hopVoiTab(r, "cho_xac_nhan")).length}
          tone="warning"
          icon={<CalendarClock className="size-5 text-warning" />}
          onSelect={() => chonLoc("cho_xac_nhan")}
          active={tab === "cho_xac_nhan"}
        />
        <StatCard
          label="Đã hoàn thành"
          value={rows.filter((r) => hopVoiTab(r, "examined")).length}
          tone="success"
          icon={<CheckCircle2 className="size-5 text-success" />}
          onSelect={() => chonLoc("examined")}
          active={tab === "examined"}
        />
      </StatRow>

      {tab !== "all" ? (
        <div className="flex items-center gap-2 text-sm text-ink-muted">
          <span>Đang lọc theo ô số đã chọn</span>
          <button
            type="button"
            onClick={() => setTab("all")}
            className="rounded-control px-2 py-0.5 font-medium text-brand-700 underline-offset-2 hover:underline"
          >
            Bỏ lọc, xem tất cả khách hàng
          </button>
        </div>
      ) : null}

      {/* MỘT HÀNG DUY NHẤT: ô tìm + "Bộ lọc", ngồi ngay trên cột danh sách.

          Trước đây chỗ này là BA hàng chồng nhau — nút "Thêm khách hàng" đứng
          một mình một hàng, rồi một thẻ trắng chứa ô tìm + ô "Bộ lọc", rồi bốn
          nút kỳ lọc dạt sang phải. Ba hàng cho hai thao tác, và bốn nút kỳ lọc
          nằm cách ô "Bộ lọc" gần trọn chiều ngang màn hình dù chúng là cùng một
          việc: thu hẹp danh sách bên dưới.

          Quang chốt 09/08/2026: gộp kỳ lọc VÀO "Bộ lọc" dạng toggle, bỏ hàng
          trên cùng và nút "Thêm khách hàng".

          NÚT "THÊM KHÁCH HÀNG" ĐI ĐÂU: khách mới của CSKH sinh ra ở màn Đặt
          lịch ("+ Đặt lịch hẹn cho khách mới" — cùng một biểu mẫu
          NewPatientForm, kèm luôn lịch hẹn đầu tiên). Trang /patients/new vẫn
          còn nguyên và gõ thẳng URL vẫn vào được. */}
      <div className="flex min-h-10 min-w-[240px] max-w-md items-center gap-2 rounded-xl border border-line bg-surface pl-3 pr-1.5 text-ink-muted shadow-card focus-within:border-brand-500">
        <Search className="size-4 shrink-0" aria-hidden="true" />
        <input
          value={term}
          onChange={(event) => setTerm(event.target.value)}
          placeholder="Tìm theo tên, số điện thoại, mã khách hàng"
          className="min-w-0 flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-ink-faint"
        />
        <BoLoc
          period={period}
          by={by}
          onChon={(kyMoi, chieuMoi) => go(kyMoi, term, chieuMoi)}
        />
      </div>

      {/* BA CỘT KHI ĐANG CHỌN MỘT KHÁCH: danh sách hẹp — VÙNG LÀM VIỆC rộng —
          hồ sơ.
          Quang (08/08/2026): *"tôi muốn vùng làm việc của mỗi khách hàng to như
          này"*. Trước đây chỗ giữa là phần cuộn ngang của bảng: bốn cột chữ mà
          muốn đọc phải kéo ngang, và đọc xong cũng chỉ biết khách ĐANG ở đâu.
          Nay khi đã chọn một khách thì danh sách co lại còn tên + trạng thái,
          nhường chỗ cho chuỗi bước. */}
      <div
        className={`grid items-start gap-3 ${
          selected
            ? "xl:grid-cols-[minmax(220px,0.8fr)_minmax(0,1.6fr)_minmax(300px,360px)]"
            : "grid-cols-1"
        }`}
      >
        <section
          aria-label="Danh sách khách hàng"
          className="min-w-0 overflow-hidden rounded-2xl border border-line bg-surface shadow-card"
        >
          <div className="flex items-center justify-between gap-2 border-b border-line px-4 py-3">
            <div>
              <h2 className="text-sm font-semibold text-ink">Danh sách khách hàng</h2>
              <p className="mt-0.5 text-xs text-ink-muted">
                {visibleRows.length} khách hàng {isPending ? " · đang tìm…" : ""}
              </p>
            </div>
          </div>
          <div className="overflow-x-auto">
            <div className={selected ? "min-w-0" : "min-w-[960px]"}>
              {!selected && <CustomerTableHeader />}
              {visibleRows.length > 0 ? (
                <div className="divide-y divide-line">
                  {visibleRows.map((row) => {
                    const active = selected?.clinic_patient_id === row.clinic_patient_id;
                    const cskh = cskhByPatient[row.clinic_patient_id];
                    const st = customerStatus(row);
                    const dl = customerDeadline(row);

                    return (
                      <div
                        key={row.clinic_patient_id}
                        onClick={() => setSelectedId(row.clinic_patient_id)}
                        className={`grid w-full items-center gap-3 px-4 py-3 text-left transition-colors cursor-pointer ${
                          selected
                            ? "grid-cols-[minmax(0,1fr)_auto]"
                            : "grid-cols-[minmax(180px,1.2fr)_minmax(100px,0.7fr)_minmax(180px,1.2fr)_minmax(180px,1.2fr)_minmax(100px,0.7fr)_minmax(90px,0.6fr)_32px]"
                        } ${active ? "bg-brand-50/60" : "hover:bg-surface-sunken"}`}
                      >
                        <div className="min-w-0">
                          <span className="block truncate text-sm font-bold text-ink">
                            {row.full_name}
                          </span>
                          <span className="mt-0.5 block truncate font-mono text-xs text-ink-muted">
                            {row.patient_code}
                          </span>
                        </div>
                        <div className="flex flex-wrap items-center gap-1">
                          <StatusChip tone={st.tone} label={st.label} />
                          {/* TRÙNG LỊCH — cảnh báo BẤM ĐƯỢC, không phải con số
                              câm. Chip cũ ở đây đếm `so_viec_mo` (số VIỆC CSKH
                              đang mở) nhưng người đọc hiểu là số LỊCH, và bấm
                              vào không ra gì. Xem LichTrungCuaKhach.tsx. */}
                          {/* KHÁM LẦN MẤY — nhãn nhỏ, đọc từ dữ liệu thật.
                              Quang: tái khám thực chất cũng là khám lần 2,3,4,
                              nhưng tách riêng vì cần biết tái khám CHO DỊCH VỤ
                              NÀO. Nên "tái khám" thắng khi lịch có nối chuỗi;
                              còn lại chỉ đếm số lượt đã khám xong.
                              Lần đầu (0 hoặc 1 lượt) thì KHÔNG hiện gì — mọi
                              khách đều là "lần 1", một nhãn đúng với tất cả
                              thì không nói thêm được gì. */}
                          {nhanLanKham(apptByPatient[row.clinic_patient_id]) && (
                            <span className="rounded-full bg-brand-50 px-1.5 py-0.5 text-[10px] font-semibold text-brand-700">
                              {nhanLanKham(apptByPatient[row.clinic_patient_id])}
                            </span>
                          )}
                          {/* CÒN N VIỆC KHÁC — nói ra, để chip không bị đọc là
                              "tất cả những gì khách này đang có".

                              Chip trạng thái là VIỆC GẤP NHẤT của khách, và nó
                              có thể thuộc một lượt khác lượt đang mở ở cột
                              giữa: Nguyễn Thị Hoa hiện "Đã check-in" trong khi
                              đang có ba việc ở ba lượt. Hai cột đều đúng, nhưng
                              đọc cạnh nhau thì trông như lệch — trừ khi màn nói
                              thẳng rằng còn việc khác. */}
                          {(trangThaiByPatient[row.clinic_patient_id]
                            ?.so_viec_mo ?? 0) > 1 && (
                            <span
                              className="rounded-full bg-surface-sunken px-1.5 py-0.5 text-[10px] font-medium text-ink-muted"
                              title="Chip bên cạnh là việc gấp nhất; khách còn việc khác, có thể ở lượt khám khác."
                            >
                              +
                              {(trangThaiByPatient[row.clinic_patient_id]
                                ?.so_viec_mo ?? 1) - 1}{" "}
                              việc
                            </span>
                          )}
                          {(apptByPatient[row.clinic_patient_id]?.sapToi
                            ?.length ?? 0) > 1 && (
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setXemTrung(row.clinic_patient_id);
                              }}
                              className="inline-flex items-center gap-1 rounded-full border border-warning/50 bg-warning-bg px-1.5 py-0.5 text-[10px] font-semibold text-warning hover:bg-warning/20"
                            >
                              <AlertTriangle className="size-3" />
                              {apptByPatient[row.clinic_patient_id]!.sapToi
                                .length}{" "}
                              lịch trùng
                            </button>
                          )}
                        </div>
                        {!selected && (
                          <>
                            <div className="min-w-0 truncate text-xs text-ink-soft">
                              {tomTatTuongTac(
                                tuongTacByPatient[row.clinic_patient_id],
                              ) ??
                                cskh?.lastInteraction ??
                                "—"}
                            </div>
                            <div className="min-w-0">
                              <span className="truncate text-xs font-medium text-ink">
                                {customerNextStep(row) ?? cskh?.nextStep ?? "—"}
                              </span>
                            </div>
                            <div>
                              <span
                                className={`text-xs font-semibold ${
                                  dl.overdue
                                    ? "rounded-md bg-danger-bg px-2 py-0.5 font-bold text-danger"
                                    : "text-ink-muted"
                                }`}
                              >
                                {dl.text}
                              </span>
                            </div>
                            <div className="truncate text-xs font-medium text-ink">
                              {/* CỘT NÀY TỪNG MANG NHÃN "PHỤ TRÁCH" — SAI.
                                  Nó hiện NGƯỜI CHẠM GẦN NHẤT (dòng cuối trong
                                  sổ tương tác), không phải người được giao
                                  việc. Hai thứ khác nhau, và gọi nhầm tên thì
                                  trưởng ca đọc bảng này rồi kết luận "việc của
                                  chị Hằng" cho một việc chưa giao cho ai —
                                  chị Hằng chỉ tình cờ là người gọi lần trước.

                                  GIAO VIỆC THẬT CHƯA CÓ và không giả vờ ở đây:
                                  `v_trang_thai_cskh` suy lại việc mỗi lần đọc
                                  nên không có chỗ nào giữ "ai nhận", còn
                                  `cskh_action.assignee` là một chuỗi tên nhập
                                  từ Notion trên một bảng đang rỗng. Muốn có
                                  người phụ trách thật thì cần một bảng phân
                                  công + nút "nhận việc" — chưa làm. */}
                              {tuongTacByPatient[row.clinic_patient_id]?.[0]
                                ?.nhan_vien ??
                                cskh?.assignee ?? (
                                  <span className="text-ink-faint">
                                    Chưa ai xử lý
                                  </span>
                                )}
                            </div>
                            <div className="text-right">
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setSelectedId(row.clinic_patient_id);
                                }}
                                className="rounded-lg p-1 text-ink-muted hover:bg-surface-sunken hover:text-ink"
                              >
                                ⋮
                              </button>
                            </div>
                          </>
                        )}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="px-4 py-14 text-center text-sm text-ink-muted">
                  {term.trim()
                    ? "Không tìm thấy khách khớp từ khoá."
                    : "Không có khách hàng trong khoảng lọc này."}
                </p>
              )}
            </div>
          </div>
        </section>

        {selected && (
          <VungLamViecKhach
            tenKhach={selected.full_name}
            clinicPatientId={selected.clinic_patient_id}
            // MỘT VẬT, KHÔNG PHẢI VẬT LAI.
            //
            // Chỗ này từng lấy `id` từ `selectedAppt.appt` (chỉ có khi lịch còn
            // đổi/huỷ được) và `status` từ `selectedAppt` (lịch đại diện) —
            // hai nguồn khác nhau. Lượt đã COMPLETED thì `appt` không tồn tại,
            // nên `lich` mang trạng thái của một lượt và id của không lượt nào,
            // và `lichSuLuotNay` lặng lẽ mở ra sổ của CẢ KHÁCH.
            lich={luotDangXem ?? EMPTY_LUOT}
            // VIỆC CỦA CHÍNH LƯỢT NÀY, không phải việc gấp nhất của cả khách.
            //
            // Ca Cường 10/08/2026: lượt hôm qua đang CHECKED_IN nên việc thắng
            // của khách là `DA_CHECKIN`; mở lượt tái khám ngày mai thì node "Đã
            // check-in" vẫn sáng "đang ở đây" trên một lượt khách chưa từng
            // đến. `v_viec_cskh` giữ đủ mọi việc kèm `appointment_id` để lọc.
            viecCuaLuot={viecCuaLuot}
            lichSu={tuongTacByPatient[selected.clinic_patient_id] ?? []}
            dangChon={viecDangGhi}
            onLamViec={(ma) => setViecDangGhi(ma)}
            onDatLich={(kieu) => setDatLich(kieu)}
            henGoiLai={henGoiLaiByPatient[selected.clinic_patient_id] ?? []}
            ghiChu={ghiChuChung}
            onGhiChuXong={() => setGhiChuChung("")}
          >
            {/* LỊCH SỬ TRƯỚC, PHẢN HỒI SAU — Quang chốt "bên trên phản hồi của
                khách hàng, thêm 1 ô nữa". Đọc lại chuyện đã xảy ra rồi mới tới
                chỗ ghi chuyện khách nói.

                VÀ NAY BẤM ĐƯỢC. Đây là chỗ DUY NHẤT trên màn liệt kê đủ mọi
                lượt của khách, nên nó cũng là chỗ tự nhiên để chọn lượt muốn
                làm việc — thay vì để server đoán một lượt cho cả khách. */}
            <LichSuCacLanKham
              chuoi={lichSuKhamByPatient[selected.clinic_patient_id] ?? []}
              luotDangXem={luotDangXem?.id ?? null}
              onChonLuot={chonLuot}
            />
            <PhanHoiKhach
              clinicPatientId={selected.clinic_patient_id}
              items={phanHoiByPatient[selected.clinic_patient_id] ?? []}
            />
            {/* Khối NHẮC TÁI KHÁM đã bỏ khỏi đây — Quang chốt 09/08/2026, vùng
                dưới chỉ còn "Phản hồi của khách". Sáng cùng ngày nó vừa được
                gộp TỪ màn /nhac-tai-kham về đây; ô "GỌI NHẮC ĐI KHÁM" ở cột
                phải làm đúng việc ấy nên hai khối chồng nhau. */}
          </VungLamViecKhach>
        )}

        {selected && (
          <aside
            aria-label="Chi tiết khách hàng"
            className="min-h-[420px] rounded-2xl border border-line bg-surface p-4 shadow-card xl:max-h-[720px] xl:overflow-y-auto animate-in fade-in duration-150"
          >
          {selected ? (
            <>
              <div className="flex items-start gap-3 border-b border-line pb-4">
                <span className="grid size-11 shrink-0 place-items-center rounded-full bg-surface-sunken text-sm font-semibold text-ink-soft">
                  {initials(selected.full_name)}
                </span>
                <div className="min-w-0 flex-1">
                  <h2 className="truncate text-base font-semibold text-ink">{selected.full_name}</h2>
                  <p className="mt-0.5 font-mono text-xs text-ink-muted">{selected.patient_code}</p>
                  <p className="mt-1 text-sm text-ink-muted">
                    {selected.phone_primary ?? "Chưa có số điện thoại"}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedId(null)}
                  aria-label="Đóng chi tiết khách hàng"
                  className="rounded-control p-1.5 text-ink-muted hover:bg-surface-sunken hover:text-ink"
                >
                  <X className="size-4" aria-hidden="true" />
                </button>
              </div>

              <div className="space-y-3 py-4">
                {/* Ô NÀY NÓI VỀ LƯỢT ĐANG XEM, không phải "lịch đại diện".
                    Trước 10/08/2026 nó đọc `selectedAppt` còn cột giữa đọc một
                    thứ khác, nên hai cột cạnh nhau nói về hai lượt khác nhau. */}
                {canManage && apptSuaDuoc ? (
                  <button
                    type="button"
                    onClick={() => setEditOpen(true)}
                    className="flex w-full items-start gap-2 rounded-control border border-line bg-surface-muted p-3 text-left hover:border-brand-500"
                  >
                    <CalendarClock className="mt-0.5 size-4 shrink-0 text-brand-700" aria-hidden="true" />
                    <span>
                      {/* LỊCH CHƯA CÓ BÁC SĨ LÀ LỊCH DỰ KIẾN, không phải lịch
                          chắc. Gọi nó là "Lịch hẹn sắp tới" rồi để CSKH đọc cho
                          khách nghe là hứa một buổi khám mà chưa ai biết ai
                          khám — quản lý còn phải xếp ca rồi gán người, và giờ
                          có thể lệch đi. Nói đúng tên nó ngay tại đây. */}
                      <span className="block text-xs text-ink-muted">
                        {!apptSuaDuoc.doctor_id
                          ? "Lịch dự kiến"
                          : nhanLuot(luotDangXem)}
                      </span>
                      <span className="mt-1 block text-sm font-semibold text-ink">
                        {fmtDateTimeOrDate(luotDangXem?.slot_start ?? null)}
                      </span>
                      {selectedAppt?.qua_gio_hen &&
                        luotDangXem?.id === selectedAppt.id && (
                          <span className="mt-1 block rounded-md bg-danger-bg px-2 py-1 text-xs font-semibold text-danger">
                            ⚠ Đã quá giờ hẹn — khách chưa check-in. Gọi hỏi khách
                            còn đến không, hoặc đánh dấu không đến.
                          </span>
                        )}
                      {!apptSuaDuoc.doctor_id && (
                        <span className="mt-1 block text-xs font-semibold text-warning">
                          Bác sĩ: chờ quản lý xác nhận
                        </span>
                      )}
                      {/* QUẢN LÝ ĐÃ ĐỔI GIỜ SO VỚI GIỜ CSKH HẸN VỚI KHÁCH.
                          Khách đã được nghe một giờ; nếu người gọi xác nhận
                          không biết là nó đã đổi thì họ đọc lại đúng giờ cũ. */}
                      {tuongTacByPatient[selected.clinic_patient_id]?.find(
                        (d) => d.trang_thai_ma === "QUAN_LY_DOI_GIO",
                      ) && (
                        <span className="mt-1 block rounded-md bg-warning-bg px-2 py-1 text-xs font-semibold text-warning">
                          ⚠ Quản lý đã đổi giờ so với giờ hẹn ban đầu — gọi báo
                          khách trước khi xác nhận.
                        </span>
                      )}
                      <span className="mt-1 block text-xs text-brand-700">Bấm để đổi hoặc hủy lịch</span>
                    </span>
                  </button>
                ) : (
                  <div className="rounded-control border border-line bg-surface-muted p-3">
                    <p className="text-xs text-ink-muted">
                      {nhanLuot(luotDangXem)}
                    </p>
                    <p className="mt-1 text-sm font-semibold text-ink">
                      {luotDangXem?.slot_start
                        ? fmtDateTimeOrDate(luotDangXem.slot_start)
                        : "Chưa có lịch hẹn"}
                    </p>
                    {selectedAppt?.qua_gio_hen &&
                      luotDangXem?.id === selectedAppt.id && (
                        <p className="mt-1 rounded-md bg-danger-bg px-2 py-1 text-xs font-semibold text-danger">
                          ⚠ Đã quá giờ hẹn — khách chưa check-in.
                        </p>
                      )}
                  </div>
                )}

                {/* LÝ DO HUỶ — HIỆN RA, KHÔNG CHỈ LƯU.
                    Quang 10/08/2026: *"khi ấn huỷ hẹn, ghi lý do, thì cần có
                    chỗ để hiện ra chỗ đó mỗi khi vào xem chứ lưu mà không hiện
                    thì không tốt"*. `booking_service` vẫn ghi đủ ba thứ (mã,
                    chữ tự viết, giờ huỷ) từ lâu; thiếu đúng đường đọc.
                    Đặt NGAY DƯỚI ô lịch vì người sắp gọi khách cần biết lý do
                    đã ghi TRƯỚC khi hỏi lại lý do thật. */}
                {luotDangXem?.status === "CANCELLED" &&
                  (luotDangXem.ly_do_huy_ma ||
                    luotDangXem.cancellation_reason) && (
                    <div className="rounded-control border border-danger/30 bg-danger-bg/40 p-3">
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-danger">
                        Lý do huỷ đã ghi
                      </p>
                      {luotDangXem.ly_do_huy_ma && (
                        <p className="mt-1 text-xs font-medium text-ink">
                          {nhanLyDoHuy(luotDangXem.ly_do_huy_ma)}
                        </p>
                      )}
                      {luotDangXem.cancellation_reason && (
                        <p className="mt-0.5 text-xs italic text-ink-soft">
                          “{luotDangXem.cancellation_reason}”
                        </p>
                      )}
                      {luotDangXem.cancelled_at && (
                        <p className="mt-1 font-mono text-[11px] text-ink-muted">
                          huỷ lúc {fmtDateTimeOrDate(luotDangXem.cancelled_at)}
                        </p>
                      )}
                    </div>
                  )}

                {/* CSKH & Lễ tân: Khung Xác nhận lịch hẹn & Gọi điện */}
                <div className="space-y-2 rounded-2xl border border-brand-200 bg-brand-50/50 p-3 text-xs shadow-xs">
                  {/* TIÊU ĐỀ NÓI ĐÚNG VIỆC ĐANG PHẢI LÀM.
                      Trước đây nó cứng là "XÁC NHẬN LỊCH HẸN & TƯƠNG TÁC" cho
                      mọi khách, kể cả người đang ở bước "Hỏi đơn vị xét
                      nghiệm" — một tiêu đề không đổi theo việc thì không nói
                      gì, và bốn cái nút bên dưới cũng vậy (xem HANH_DONG trong
                      GhiTuongTac). */}
                  <div className="flex items-center justify-between gap-2 font-bold text-brand-800">
                    <span className="uppercase">
                      {/* TIÊU ĐỀ THEO VIỆC CỦA LƯỢT ĐANG XEM.
                          Đọc `trangThaiByPatient` ở đây là lấy việc gấp nhất
                          của CẢ KHÁCH — với Cường, đó là "Đã check-in" của lượt
                          hôm qua, in lên trên một lượt ngày mai. */}
                      {tieuDeHanhDong(
                        viecDangGhi ?? viecCuaLuot[0]?.trang_thai,
                      )}
                    </span>
                    <span className="shrink-0 rounded-full bg-brand-200 px-2 py-0.5 text-[10px] text-brand-800 font-mono">
                      CSKH / Lễ tân
                    </span>
                  </div>

                  {/* GỌI XONG THÌ GHI LẠI.
                      Trước đây chỗ này là một thẻ `<a href="tel:">` và một nút
                      "Zalo/SMS" gắn cứng disabled. Quay số xong hệ thống không
                      biết gì, nên cột "Tương tác gần nhất" hiện "—" cho mọi
                      khách kể cả những người vừa được gọi sáng nay. */}
                  {/* BỘ NÚT RIÊNG CHO TRẠNG THÁI ĐANG CHỌN — đặc tả chị Thu.
                      Mỗi trạng thái một bộ khác nhau: gọi xác nhận thì hiện số
                      khách, hỏi xét nghiệm thì hai nút Có/Chưa, chờ chuyên môn
                      thì mở luôn chỗ tải kết quả lên. */}
                  <div className="pt-1">
                    <HanhDongTrangThai
                      key={`${selected.clinic_patient_id}-${viecDangGhi ?? ""}`}
                      trangThai={
                        viecDangGhi ?? viecCuaLuot[0]?.trang_thai ?? null
                      }
                      clinicPatientId={selected.clinic_patient_id}
                      // CÙNG MỘT LƯỢT VỚI CỘT GIỮA.
                      //
                      // Chỗ này từng đọc `appt?.id` — chỉ có khi lịch còn
                      // đổi/huỷ được — nên với một lượt đã khám xong, đã huỷ,
                      // hoặc với bốn vai không có quyền đổi lịch, nó xuống null
                      // và MỌI thao tác thuộc `CAN_LICH_HEN` trả 422 "Việc này
                      // phải gắn với một lịch hẹn cụ thể". Ghi lý do huỷ là một
                      // trong số đó: nút có, bấm không bao giờ ăn.
                      appointmentId={luotDangXem?.id ?? null}
                      phone={selected.phone_primary}
                      tepKetQua={tepByPatient[selected.clinic_patient_id] ?? []}
                      daXong={false}
                      ghiChu={ghiChuChung}
                      onGhiChu={setGhiChuChung}
                    />
                  </div>


                  {/* KHÔNG CÒN NÚT "XÁC NHẬN KHÁCH SẼ TỚI".
                      Quang (2026-08-04): lịch hẹn sinh ra từ chính cuộc gọi
                      hoặc tin nhắn với bệnh nhân, nên nó đã chắc ngay lúc đặt
                      — gọi lại để xác nhận cái vừa thoả thuận là làm hai lần
                      một việc. Đổi hoặc huỷ thì bấm vào "Lịch hẹn sắp tới" ở
                      trên, và phải ghi lý do.

                      "Báo không tới" cũng bỏ khỏi đây: đánh vắng là việc của
                      Lễ tân TẠI THỜI ĐIỂM bệnh nhân không đến, không phải việc
                      CSKH đoán trước qua điện thoại. */}
                  <div className="space-y-1.5 pt-1">
                    {/* CHƯA CÓ BÁC SĨ → việc của CSKH là báo quản lý, không
                        phải tự chọn: họ không biết ai trực tuần đó. Nút chỉ
                        hiện khi lịch thật sự còn trống bác sĩ. */}
                    {apptSuaDuoc && !apptSuaDuoc.doctor_id && (
                      <BaoXepBacSi appointmentId={apptSuaDuoc.id} />
                    )}
                    <button
                      type="button"
                      disabled={!canManage || !apptSuaDuoc}
                      title={
                        apptSuaDuoc
                          ? "Đổi giờ hoặc huỷ lượt đang xem"
                          : "Lượt đang xem đã đóng hoặc đã huỷ — không đổi được nữa"
                      }
                      onClick={() => setEditOpen(true)}
                      className="w-full inline-flex items-center justify-center gap-1.5 rounded-xl border border-line bg-surface py-2 px-3 text-xs font-semibold text-ink-soft hover:bg-surface-muted disabled:opacity-50"
                    >
                      Đổi / huỷ lịch hẹn (ghi lý do)
                    </button>
                  </div>

                </div>

                {canEdit && !selectedAppt?.upcoming ? (
                  <button
                    type="button"
                    // ĐI TỚI MÀN ĐẶT LỊCH THẬT, KHÔNG MỞ MODAL NỮA.
                    //
                    // `QuickBookingModal` render `CskhBookingGrid` — một màn
                    // DỰNG SẴN: tên "Nguyễn Văn An", "BS. Trần Minh Đức", khung
                    // giờ 08:00–17:15 viết cứng, nhãn "Sắp ra mắt v2". Không có
                    // dòng nào chạm tới lịch thật, nên CSKH bấm "Đặt lịch hẹn"
                    // trong đó là không có gì được lưu.
                    //
                    // `?bn=` mang mã bệnh nhân sang để màn kia chọn sẵn khách —
                    // BookingHub đọc tham số này (xem useSearchParams ở đó).
                    onClick={() =>
                      router.push(
                        `/appointments?bn=${encodeURIComponent(selected.patient_code ?? "")}`,
                      )
                    }
                    className="flex min-h-10 w-full items-center justify-center gap-2 rounded-control bg-brand-600 px-3 text-sm font-semibold text-white hover:bg-brand-700"
                  >
                    <CalendarClock className="size-4" aria-hidden="true" />
                    Đặt lịch mới
                  </button>
                ) : null}

                {canEdit ? (
                  <>
                    <PatientAdminEditor
                      key={selected.clinic_patient_id}
                      patient={{
                        clinic_patient_id: selected.clinic_patient_id,
                        full_name: selected.full_name,
                        date_of_birth: selected.date_of_birth,
                        phone_primary: selected.phone_primary,
                        phone_secondary: selected.phone_secondary,
                        gender: selected.gender,
                        ethnicity: selected.ethnicity,
                        nationality: selected.nationality,
                        occupation: selected.occupation,
                        patient_objection: selected.patient_objection,
                        address: selected.address,
                        guardian_name: selected.guardian_name,
                        van_de_di_kham: selected.van_de_di_kham,
                        linh_vuc: selected.linh_vuc,
                      }}
                    />
                    <dl className="space-y-1.5 text-sm">
                      <DetailRow label="Cơ sở" value={locName(selected.location_id)} />
                      <DetailRow label="Ngày tạo" value={fmtDateTimeOrDate(selected.created_at)} />
                    </dl>
                  </>
                ) : (
                  <dl className="space-y-2 text-sm">
                    <DetailRow label="Ngày sinh" value={dobDisplay(selected)} />
                    <DetailRow label="Giới tính" value={selected.gender} />
                    <DetailRow label="SĐT chính" value={selected.phone_primary} />
                    <DetailRow label="SĐT người nhà" value={selected.phone_secondary} />
                    <DetailRow label="Dân tộc" value={selected.ethnicity} />
                    <DetailRow label="Quốc tịch" value={selected.nationality} />
                    <DetailRow label="Nghề nghiệp" value={selected.occupation} />
                    <DetailRow label="Đối tượng" value={selected.patient_objection} />
                    <DetailRow label="Địa chỉ" value={selected.address} />
                    <DetailRow label="Cơ sở" value={locName(selected.location_id)} />
                    <DetailRow label="Ngày tạo" value={fmtDateTimeOrDate(selected.created_at)} />
                  </dl>
                )}

                {selectedAppt?.examined ? (
                  <Link
                    href={`/patients/${selected.clinic_patient_id}`}
                    className="flex min-h-10 items-center justify-center gap-2 rounded-control border border-brand-500 bg-surface px-3 text-sm font-semibold text-brand-700 hover:bg-brand-50"
                  >
                    <ExternalLink className="size-4" aria-hidden="true" />
                    Hồ sơ và lịch sử khám
                  </Link>
                ) : null}
              </div>
            </>
          ) : (
            <div className="grid min-h-80 place-items-center text-center">
              <div>
                <UsersRound className="mx-auto size-7 text-ink-faint" aria-hidden="true" />
                <p className="mt-3 text-sm font-medium text-ink">Chọn một khách hàng</p>
                <p className="mt-1 text-xs text-ink-muted">
                  Thông tin hành chính và lịch hẹn sẽ hiện ở đây.
                </p>
              </div>
            </div>
          )}
        </aside>
        )}
      </div>

      {editOpen && selected && selectedAppt?.appt ? (
        <AppointmentEditModal
          appt={selectedAppt.appt}
          patientName={selected.full_name}
          clinicPatientId={selected.clinic_patient_id}
          services={services}
          doctors={doctors}
          locations={locations}
          onClose={() => setEditOpen(false)}
        />
      ) : null}

      {/* Bảng "khách này đang có mấy lịch". Mở từ chip cảnh báo ở danh sách
          bên trái, nên nó KHÔNG phụ thuộc khách đang được chọn — CSKH thấy
          cảnh báo ở dòng nào thì mở đúng dòng ấy. */}
      {xemTrung && apptByPatient[xemTrung]?.sapToi?.length ? (
        <LichTrungCuaKhach
          tenKhach={
            rows.find((r) => r.clinic_patient_id === xemTrung)?.full_name ??
            "Khách hàng"
          }
          lich={apptByPatient[xemTrung]!.sapToi}
          onDong={() => setXemTrung(null)}
          onDaHuy={() => router.refresh()}
        />
      ) : null}

      {/* Form đặt lịch ngay tại màn này — tái khám hoặc khám mới. */}
      {datLich && selected ? (
        <DatLichModal
          tenKhach={selected.full_name}
          clinicPatientId={selected.clinic_patient_id}
          services={services}
          doctors={doctors}
          locations={locations}
          defaultLocationId={selected.location_id ?? undefined}
          // TÁI KHÁM NỐI VÀO LƯỢT ĐANG XEM, không vào "lượt xong gần nhất".
          //
          // `lanKhamGanNhat` là max(slot_start) trong các lịch COMPLETED của
          // KHÁCH. Khách có hai đợt song song (Phụ khoa + Nội tiết) thì nó khoá
          // dịch vụ theo đợt kia, bất kể người trực đang đọc đợt nào — và
          // `lich_truoc_id` cũng nối sai chuỗi, âm thầm.
          khoaDichVu={
            datLich === "tai-kham" && luotDangXem?.service_type_id
              ? {
                  serviceId: luotDangXem.service_type_id,
                  label: luotDangXem.service_name ?? "Dịch vụ của lượt này",
                }
              : undefined
          }
          lichTruocId={
            datLich === "tai-kham" ? (luotDangXem?.id ?? undefined) : undefined
          }
          onDong={() => setDatLich(null)}
          // ĐẶT XONG THÌ CHUYỂN HẲN SANG LƯỢT MỚI.
          //
          // Quang 10/08/2026: *"khi thực hiện lịch tái khám… vẫn đang hiển thị
          // các thao tác của quản lý khách cũ nên không thao tác được với lượt
          // khám mới"*. Trước đây `onXong` chỉ `router.refresh()`, và server
          // tính lại vẫn ra đúng lượt cũ — nên màn không đổi một pixel, chỉ ô
          // Lịch sử ở tận cuối trang mọc thêm một dòng.
          //
          // Đây là chỗ DUY NHẤT trong cả luồng BIẾT CHẮC người dùng vừa tạo
          // lượt nào. Mọi luật suy diễn khác rồi cũng sai ở một ca nào đó.
          onXong={(appointmentId) => {
            setDatLich(null);
            if (appointmentId && selected) {
              setLuotChon({ pid: selected.clinic_patient_id, id: appointmentId });
              setViecDangGhi(null);
            }
            router.refresh();
          }}
        />
      ) : null}
    </div>
  );
}

/** Nhãn "khám lần mấy" cho một khách. `null` = không đáng hiện.
 *
 *  ƯU TIÊN "tái khám" HƠN CON SỐ. Cả hai đều đúng — tái khám thì đương nhiên
 *  cũng là lần thứ N — nhưng "tái khám" nói thêm được một điều mà con số không
 *  nói: lượt này nối tiếp lượt trước, cùng một dịch vụ, cùng một câu chuyện.
 *  Đó chính là chỗ Quang muốn phân biệt.
 *
 *  KHÔNG HIỆN "lần 1". Khách nào cũng từng là lần 1; một nhãn đúng với tất cả
 *  thì chỉ tốn chỗ và dạy người đọc bỏ qua vùng ấy. */
export function nhanLanKham(a?: ApptInfo): string | null {
  if (!a) return null;
  if (a.laTaiKham) return "tái khám";
  if (a.soLanKham >= 2) return `khám lần ${a.soLanKham}`;
  return null;
}

function DetailRow({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="grid grid-cols-[7.5rem_minmax(0,1fr)] gap-2">
      <dt className="text-ink-muted">{label}</dt>
      <dd className="min-w-0 break-words text-ink">{value || "—"}</dd>
    </div>
  );
}

function dobDisplay(row: CustomerRow): string | null {
  if (row.birth_year) return `${row.birth_year} (chỉ năm)`;
  return row.date_of_birth ? fmtDate(row.date_of_birth) : null;
}
