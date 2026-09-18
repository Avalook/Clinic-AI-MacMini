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
import { nhanLoi } from "@/lib/loi-api";
import { nowMs } from "@/lib/datetime";
import { khoaThaoTac, xongThaoTac, dinhDanhThaoTac } from "./khoa-mot-lan";
import { useRouter } from "next/navigation";
import { Check, Phone, CircleDashed, Undo2, Lock } from "lucide-react";
import { nhanLyDoHuy } from "@/lib/ly-do-huy";
import { MOT_CHAM, kenhCho, nhanLanChamCuoi } from "./mot-cham";
import type { DongLichSu } from "./so-tuong-tac";
import type { HenGoiLai, ViecDoiTac } from "./CustomersView";
import type { MocTaiKham } from "./NhacTaiKham";
import type { MaXacMinh } from "@/lib/xac-minh";
import type { TepKetQuaRow } from "./TepKetQua";

/** MỘT Ô TRÊN DÒNG TRẠNG THÁI KHÁCH (Tuyền chốt 16/09/2026).
 *
 *  HAI LOẠI Ô, và phân biệt là cả mục đích của bản viết lại này:
 *
 *    · Ô CSKH — việc CSKH tự làm (gọi xác nhận lịch, hẹn gọi lại, không gọi
 *      được). BẤM VÒNG TRÒN là ghi vào sổ chăm sóc (tính KPI); bấm lại ô đã
 *      tích là hoàn tác — dòng vẫn nằm trong sổ, chỉ thôi được tính.
 *    · Ô KHOÁ — trạng thái do NGƯỜI KHÁC tạo (lễ tân check-in/checkout, đối tác
 *      gửi kết quả, bác sĩ cho phép gửi, bác sĩ quyết theo dõi thủ thuật). Chỉ
 *      đồng bộ sang cho CSKH biết; vòng tròn không bấm được. Tuyền: *"không cho
 *      thao tác với nút tròn của node này nhé không là mâu thuẫn đấy"*.
 *
 *  Bỏ hẳn nút "Làm bước này": vòng tròn là nút.
 *
 *  Ở CẤP MODULE, không lồng trong `VungLamViecKhach`: component tạo ra trong
 *  lúc render thì React dựng lại từ đầu mỗi lần vẽ. */
function OBuoc({
  ten,
  viec,
  xong,
  dang,
  nguon,
  onBam,
  dangGhi = false,
  lan,
  chon = false,
  onChon,
  canhBao,
  ghiChuThem,
  loi,
}: {
  ten: string;
  viec: string;
  xong: boolean;
  dang: boolean;
  /** Có = ô KHOÁ, nói ra ai tạo trạng thái này ("lễ tân", "bác sĩ"…). */
  nguon?: string;
  /** Bấm vòng tròn. Chỉ ô CSKH mới có. */
  onBam?: () => void;
  dangGhi?: boolean;
  lan?: DongLichSu;
  chon?: boolean;
  /** Bấm tên → khối hành động bên phải đổi theo ô này. */
  onChon?: () => void;
  /** Dòng chữ ĐỎ cảnh báo thời gian (theo dõi sau thủ thuật). */
  canhBao?: string | null;
  ghiChuThem?: React.ReactNode;
  loi?: string | null;
}) {
  const lop = `flex size-7 shrink-0 items-center justify-center rounded-full border-2 ${
    xong
      ? "border-success bg-success-bg text-success"
      : dang
        ? "border-brand-600 bg-brand-50 text-brand-700"
        : "border-line bg-surface-muted text-ink-faint"
  }`;
  const ruot = dangGhi ? (
    <Undo2 className="size-3.5 animate-pulse" />
  ) : xong ? (
    <Check className="size-4" strokeWidth={3} />
  ) : nguon ? (
    <Lock className="size-3" />
  ) : dang ? (
    <Phone className="size-3.5" />
  ) : (
    <CircleDashed className="size-3.5" />
  );
  const vong =
    onBam && !nguon ? (
      <button
        type="button"
        onClick={onBam}
        disabled={dangGhi}
        title={
          xong
            ? "Bấm lại để hoàn tác — dòng vẫn nằm trong sổ chăm sóc"
            : "Bấm để đánh dấu đã làm xong"
        }
        aria-label={xong ? `Hoàn tác: ${ten}` : `Đánh dấu đã xong: ${ten}`}
        aria-pressed={xong}
        className={`${lop} ring-1 ring-inset ring-brand-300 hover:ring-2 hover:ring-brand-500 disabled:opacity-50`}
      >
        {ruot}
      </button>
    ) : (
      <span
        className={lop}
        title={nguon ? `Tự đồng bộ từ ${nguon} — CSKH không tích ô này` : undefined}
      >
        {ruot}
      </span>
    );

  return (
    <div
      className={`flex gap-3 rounded-card p-2 ${chon ? "bg-surface-selected" : ""}`}
    >
      {vong}
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          {onChon ? (
            <button
              type="button"
              onClick={onChon}
              className={`text-left text-sm underline-offset-2 hover:underline ${
                xong ? "font-medium text-ink" : dang ? "font-semibold text-brand-700" : "text-ink-soft"
              }`}
            >
              {ten}
            </button>
          ) : (
            <span
              className={`text-sm ${
                xong ? "font-medium text-ink" : dang ? "font-semibold text-brand-700" : "text-ink-soft"
              }`}
            >
              {ten}
            </span>
          )}
          {dang && !xong && (
            <span className="rounded-chip bg-brand-100 px-2 py-0.5 text-label font-bold text-brand-800">
              đang ở đây
            </span>
          )}
          {nguon && (
            <span className="rounded-chip bg-surface-sunken px-1.5 py-0.5 text-label font-medium text-ink-muted">
              từ {nguon}
            </span>
          )}
        </div>
        <p className="mt-0.5 text-label leading-snug text-ink-muted">{viec}</p>
        {lan && (
          <p className="mt-1 text-label leading-snug text-ink-soft">
            <span className="font-mono text-ink-muted">{gio(lan.xay_ra_luc)}</span>
            {lan.ket_qua && ` · ${NHAN_KET_QUA[lan.ket_qua] ?? lan.ket_qua}`}
            {lan.nhan_vien && ` · ${lan.nhan_vien}`}
            {lan.noi_dung && (
              <span className="block italic text-ink-muted">“{lan.noi_dung}”</span>
            )}
          </p>
        )}
        {canhBao && (
          <p className="mt-1 text-label font-semibold text-danger">{canhBao}</p>
        )}
        {ghiChuThem}
        {loi && <p className="mt-1 text-label text-danger">{loi}</p>}
      </div>
    </div>
  );
}
/** Bốn kết quả của một cuộc gọi nhắc — cùng bộ từ với `RecallCallResult` ở
 *  backend và với CHECK ở database. Gửi mã ngoài bốn cái này là 422. */
// Trường tên `ketQua`, KHÔNG phải `ma`: đây là `ket_qua` của một cuộc gọi, không
// phải mã trạng thái. `cskh-trang-thai-drift` quét `ma:` để gom mã trạng thái ở
// cột giữa, nên đặt trùng tên là kéo bốn mã này vào một danh sách chúng không
// thuộc về — bài kiểm ấy đã bắt được đúng chuyện đó.
/** Một lối ra của cuộc gọi nhắc tái khám. */
interface LoiRa {
  /** `ket_qua` gửi lên backend. */
  ketQua: string;
  ten: string;
}

const KET_QUA_GOI_NHAC: LoiRa[] = [
  { ketQua: "DA_LIEN_HE", ten: "Đã liên hệ được" },
  { ketQua: "CHUA_NGHE_MAY", ten: "Không nghe máy" },
  { ketQua: "TU_CHOI", ten: "Khách từ chối" },
  { ketQua: "CAN_BAC_SI", ten: "Cần bác sĩ xem" },
];

/** MỘT VIỆC GỌI NHẮC — lượt 1 mời tái khám, lượt 2 nhắc đi khám.
 *
 *  Ở CẤP MODULE, không lồng trong `VungLamViecKhach`. */
function MotViecGoiNhac({
  viec,
  dang,
  loi,
  onGhi,
}: {
  viec: MocTaiKham;
  dang: string | null;
  loi: string | null;
  onGhi: (ketQua: string) => void;
}) {
  return (
    <div
      className={`flex gap-3 rounded-xl border p-2.5 ${
        viec.qua_han ? "border-danger/40 bg-danger-bg/30" : "border-line"
      }`}
    >
      <span
        className={`flex size-7 shrink-0 items-center justify-center rounded-full border-2 ${
          viec.qua_han
            ? "border-danger bg-danger-bg text-danger"
            : "border-brand-600 bg-brand-50 text-brand-700"
        }`}
      >
        <Phone className="size-3.5" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-semibold text-ink">
            {viec.luot_goi === 1 ? "Gọi mời tái khám" : "Gọi nhắc đi khám"}
          </span>
          {viec.qua_han && (
            <span className="rounded-chip bg-danger-bg px-2 py-0.5 text-label font-bold text-danger">
              quá hạn
            </span>
          )}
        </div>
        <p className="mt-0.5 text-label leading-snug text-ink-muted">
          Hẹn quay lại {ngayVn(viec.ngay_hen)} · phải gọi trước{" "}
          {ngayVn(viec.han_goi)}
          {viec.ly_do ? ` · ${viec.ly_do}` : ""}
        </p>
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {KET_QUA_GOI_NHAC.map((k) => (
            <button
              key={k.ketQua}
              type="button"
              disabled={Boolean(dang)}
              onClick={() => onGhi(k.ketQua)}
              className="rounded-full px-2.5 py-0.5 text-label font-medium text-brand-700 ring-1 ring-inset ring-brand-300 hover:bg-brand-50 disabled:opacity-50"
            >
              {dang === viec.id + k.ketQua ? "Đang ghi…" : k.ten}
            </button>
          ))}
        </div>
        {loi && <p className="mt-1 text-label text-danger">{loi}</p>}
      </div>
    </div>
  );
}

/** MỘT LỜI HẸN GỌI LẠI — ngày, giờ, lý do, và một nút đóng nó.
 *
 *  Ở CẤP MODULE, không lồng trong `VungLamViecKhach`: component tạo ra trong
 *  lúc render thì React dựng lại từ đầu mỗi lần vẽ. */
function MotLoiHen({
  hen,
  dangDong,
  loi,
  onDong,
}: {
  hen: HenGoiLai;
  dangDong: boolean;
  loi: string | null;
  onDong: () => void;
}) {
  const homNay = new Date().toLocaleDateString("en-CA", {
    timeZone: "Asia/Ho_Chi_Minh",
  });
  const toiHan = hen.ngay_goi <= homNay;
  return (
    <div
      className={`flex gap-3 rounded-xl border p-2.5 ${
        toiHan ? "border-brand-300 bg-brand-50/50" : "border-line"
      }`}
    >
      <span
        className={`flex size-7 shrink-0 items-center justify-center rounded-full border-2 ${
          toiHan
            ? "border-brand-600 bg-brand-50 text-brand-700"
            : "border-line bg-surface-muted text-ink-faint"
        }`}
      >
        <Phone className="size-3.5" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-semibold text-ink">
            {/* GIỜ CHỈ HIỆN KHI CÓ. `gio_goi` null nghĩa là "chỉ hẹn tới ngày";
                in 00:00 vào đấy là bịa một mốc mà người trực sẽ tin. */}
            Gọi lại {hen.gio_goi ? `${hen.gio_goi.slice(0, 5)} ` : ""}ngày{" "}
            {ngayVn(hen.ngay_goi)}
          </span>
          {toiHan && (
            <span className="rounded-chip bg-brand-100 px-2 py-0.5 text-label font-bold text-brand-800">
              tới hạn
            </span>
          )}
        </div>
        <p className="mt-0.5 text-label leading-snug text-ink-soft">
          {hen.ly_do}
        </p>
        {hen.tao_boi && (
          <p className="mt-0.5 text-label text-ink-muted">
            người hẹn: {hen.tao_boi}
          </p>
        )}
        <button
          type="button"
          onClick={onDong}
          disabled={dangDong}
          className="mt-1.5 rounded-full px-2.5 py-0.5 text-label font-medium text-brand-700 ring-1 ring-inset ring-brand-300 hover:bg-brand-50 disabled:opacity-50"
        >
          {dangDong ? "Đang đóng…" : "Đã gọi xong — đóng việc"}
        </button>
        {loi && <p className="mt-1 text-label text-danger">{loi}</p>}
      </div>
    </div>
  );
}

/** Ngày dạng yyyy-mm-dd → dd/mm. */
function ngayVn(d: string): string {
  const [y, m, ngay] = d.split("-");
  return ngay && m ? `${ngay}/${m}${y ? `/${y}` : ""}` : d;
}

/** Date → "dd/mm/yyyy HH:MM" giờ Việt Nam. */
function ngayGio(d: Date): string {
  return d.toLocaleString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "Asia/Ho_Chi_Minh",
  });
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

/** LƯỢT KHÁM ĐANG XEM — đúng những gì cột giữa cần biết về một lượt.
 *
 *  ĐÂY KHÔNG CÒN LÀ "LỊCH ĐẠI DIỆN". Trước 10/08/2026 `id` và `status` của vật
 *  này đến từ HAI nguồn khác nhau ở `CustomersView` (`appt?.id` và `repr`), nên
 *  một lượt đã khám xong cho ra `status = COMPLETED` kèm `id = null`. Nay nó
 *  luôn là MỘT lượt có thật, do người dùng chọn hoặc do `luotMacDinh` chọn. */
export interface MocLich {
  id: string | null;
  status: string | null;
  slot_start: string | null;
  created_at: string | null;
  cancelled_at: string | null;
  /** Lý do huỷ CỦA LƯỢT NÀY — mã chọn sẵn, và chữ người huỷ tự viết. */
  ly_do_huy_ma: string | null;
  cancellation_reason: string | null;
  /** Dịch vụ của lượt — nút "Tái khám" khoá theo nó. */
  service_type_id: string | null;
  service_name: string | null;
  /** Bác sĩ của lượt này không còn ca KHÁM vào ngày khám. Tính ở page.tsx từ
   *  `work_roster` (station = LICH_KHAM), theo TỪNG LƯỢT. */
  mat_bac_si?: boolean;
  /** Bác sĩ bị gỡ đã có ca khám trở lại hôm đó. */
  bs_go_co_ca_lai?: boolean;
  /** `visit.closed_at` — lễ tân checkout tại quầy (ô "Checkout" chỉ đọc). */
  quay_dong_luc?: string | null;
  /** Thủ thuật của lượt + quyết định theo dõi của BÁC SĨ (20260916000001). */
  co_thu_thuat?: boolean;
  thu_thuat_xong_luc?: string | null;
  theo_doi_thu_thuat?: string | null;
  theo_doi_sau_ngay?: number | null;
  /** Việc gửi đối tác + trạng thái đối tác bấm — chỉ đọc (17/09/2026). */
  doi_tac?: ViecDoiTac[];
}

/** Câu CSKH đọc cho từng trạng thái đối tác. */
const NHAN_DOI_TAC: Record<ViecDoiTac["trang_thai"], string> = {
  CHO_LAY_MAU: "chờ lấy mẫu",
  DA_LAY_MAU: "đã lấy mẫu, chờ đối tác nhận",
  CHO_TAI_LIEU: "đối tác đang làm, chờ tài liệu",
  DA_GUI_KET_QUA: "đối tác đã gửi tài liệu",
};

export default function VungLamViecKhach({
  tenKhach,
  clinicPatientId,
  lich,
  lichSu,
  viecCuaLuot = [],
  dangChon,
  onLamViec,
  onDatLich,
  henGoiLai = [],
  taiKham = [],
  tepCuaLuot = [],
  thanhLuot,
  chipTrangThai,
  ghiChu = "",
  onGhiChuXong,
  children,
}: {
  tenKhach: string;
  clinicPatientId: string;
  lich: MocLich;
  lichSu: DongLichSu[];
  /** VIỆC ĐANG MỞ CỦA CHÍNH LƯỢT NÀY, gấp nhất trước (`v_viec_cskh`).
   *
   *  Thay cho `trangThaiHienTai` — một chuỗi duy nhất suy từ `v_trang_thai_cskh`,
   *  tức việc gấp nhất của CẢ KHÁCH. Khách có nhiều lượt thì nó nói về lượt
   *  khác: ca Cường 10/08/2026, lượt hôm qua đang CHECKED_IN nên node "Đã
   *  check-in" sáng "đang ở đây" ngay trên lượt tái khám ngày mai, và cột phải
   *  mời "Check-in cho khách" cho một người chưa từng đến.
   *
   *  Danh sách nên NHIỀU node cùng sáng được — khách có thể vừa chờ kết quả xét
   *  nghiệm vừa tới hạn nhắc hẹn, và view vẫn luôn biết cả hai. */
  viecCuaLuot?: { trang_thai: string; appointment_id: string | null }[];
  /** Trạng thái CSKH đang chọn làm việc (null = chưa chọn). */
  dangChon?: string | null;
  /** Bấm một trạng thái → khối hành động bên phải đổi theo nó. `ketQua` chỉ
   *  truyền khi bấm một lối ra cụ thể trong hàng gộp — hôm nay không hàng nào
   *  dùng tới, vì lối ra ghi thẳng. Giữ tham số cho nhóm sau. */
  onLamViec: (maTrangThai: string, ketQua?: string) => void;
  /** Mở form đặt lịch. "tai-kham" = khoá dịch vụ + nối chuỗi; "kham-moi" =
   *  chọn dịch vụ tự do, không nối chuỗi. */
  onDatLich?: (kieu: "tai-kham" | "kham-moi") => void;
  /** Lời hẹn gọi lại CHƯA ĐÓNG của khách này. */
  henGoiLai?: HenGoiLai[];
  /** Mốc gọi nhắc tái khám CÒN PHẢI GỌI của khách này. */
  taiKham?: MocTaiKham[];
  /** Tệp kết quả CỦA LƯỢT ĐANG XEM — ô "Có kết quả xét nghiệm" đọc từ đây. */
  tepCuaLuot?: TepKetQuaRow[];
  /** Thanh chọn lượt khám (ThanhLuotKham) — vẽ ở đầu vùng làm việc. */
  thanhLuot?: React.ReactNode;
  /** Chip trạng thái của khách ("Đã check-in — đang chờ khám"…).
   *
   *  VÌ SAO Ở ĐÂY CHỨ KHÔNG Ở DANH SÁCH (Tuyền 16/09/2026). Khi đã chọn một
   *  khách, cột danh sách co còn ~210px; chip này dài 191px nên nó chiếm trọn
   *  một dòng riêng dưới mỗi tên, danh sách thành một cột chữ vỡ. Cột trái chỉ
   *  còn trả lời "ai" (tên + mới/cũ); "đang ở đâu" thuộc về vùng này — chỗ đã
   *  mang tên khách và thanh chọn lượt. */
  chipTrangThai?: React.ReactNode;
  /** Ghi chú người dùng đang gõ ở CỘT PHẢI — đi kèm cú bấm một-chạm ở đây. */
  ghiChu?: string;
  /** Gọi sau khi ghi xong, để cột phải xoá ô gõ. */
  onGhiChuXong?: () => void;
  /** Khối gắn thêm bên dưới — nay chỉ còn "Phản hồi của khách". */
  children?: React.ReactNode;
}) {

  const router = useRouter();
  const [dangGhiLoiRa, setDangGhiLoiRa] = useState<string | null>(null);
  // LỖI PHẢI BIẾT NÓ THUỘC VỀ BƯỚC NÀO.
  //
  // Bản trước chỉ giữ câu chữ. Node vẽ nó với điều kiện `motCham && loiGhiLoiRa`
  // — không hỏi bước nào — nên MỘT bước hỏng là MỌI bước cùng hiện y câu ấy.
  // Tuyền gặp đúng thế 14/08/2026: chốt "chưa gửi tệp kết quả" chỉ áp cho bước
  // trả kết quả (tuong_tac_cskh_service.py, `if loai == "TRA_KQ"`), nhưng câu
  // ấy hiện dưới cả "Đã check-in", "Gọi nhắc hẹn", "Huỷ lịch", "Không cần
  // follow up" — những bước không liên quan gì tới tệp kết quả.
  //
  // Một dòng đỏ nói sai chỗ tệ hơn không có dòng nào: nó bảo người trực rằng
  // mọi bước đều đang hỏng, nên họ ngừng tin mọi dòng đỏ, kể cả dòng đúng.
  // Cùng bài học với lỗi "một bước hỏng tô đỏ cả chuỗi" hồi trước.
  const [loiGhiLoiRa, setLoiGhiLoiRa] = useState<
    { ma: string; cau: string } | null
  >(null);
  const [dangDongHen, setDangDongHen] = useState<string | null>(null);
  const [loiDongHen, setLoiDongHen] = useState<string | null>(null);
  const [loiDongHenChu, setLoiDongHenChu] = useState<string | null>(null);

  /** ĐÓNG MỘT LỜI HẸN GỌI LẠI.
   *
   *  `PATCH /api/cskh/hen-goi-lai` đã có sẵn ở BFF (route.ts) và ở backend
   *  (`HenGoiLaiService.dong`) từ 09/08 — nhưng không một màn nào gọi nó. Đó là
   *  lý do trạng thái `HEN_GOI_LAI` không có đường ra: sinh ra được, hiện ra
   *  được, và ở lại mãi mãi. */
  async function dongHen(id: string) {
    setDangDongHen(id);
    setLoiDongHen(null);
    setLoiDongHenChu(null);
    const res = await fetch("/api/cskh/hen-goi-lai", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });
    setDangDongHen(null);
    if (!res.ok) {
      const d = (await res.json().catch(() => null)) as {
        error?: string;
        message?: string;
      } | null;
      setLoiDongHen(id);
      setLoiDongHenChu(
        nhanLoi(d, `Không đóng được (lỗi ${res.status}).`),
      );
      return;
    }
    router.refresh();
  }

  /** Ghi một lần chạm vào sổ chăm sóc. Dùng chung cho lối ra của hàng gộp và
   *  cho nút "Làm bước này" một-chạm.
   *
   *  `khoa` chỉ để nút biết mình đang là cái đang quay — nó là `ket_qua` với
   *  hàng gộp (ba nút cùng hàng, phải phân biệt được cái nào) và là mã trạng
   *  thái với node timeline (mỗi node một nút). */
  async function ghiMotCham(
    ma: string,
    v: {
      loai: string;
      ketQua: string;
      noiDung: string;
      khoa: string;
      khachXacNhan?: boolean;
      /** Bắt buộc với CHECK_IN — backend từ chối nếu thiếu (15/09/2026). */
      xacMinhCach?: MaXacMinh;
    },
  ) {
    // NĂM LOẠI BẮT BUỘC GẮN LỊCH HẸN (CAN_LICH_HEN ở backend). Chặn tại đây
    // bằng một dòng đọc được, thay vì để backend trả 422 mà màn hình nuốt mất.
    const canLich = ["XAC_NHAN_LICH", "NHAC_HEN", "HOI_LY_DO_HUY", "CHECK_IN", "CHECK_OUT"];
    if (canLich.includes(v.loai) && !lich.id) {
      setLoiGhiLoiRa({
        ma: v.khoa,
        cau: "Khách chưa có lịch hẹn nào để gắn thao tác này.",
      });
      return;
    }
    // LUÔN GẮN LỊCH HẸN KHI CÓ, không chỉ với năm loại bắt buộc.
    //
    // ĐÂY LÀ LỖI QUANG BẮT ĐƯỢC 10/08/2026: *"ở lượt khám mới ấn mấy nút dưới
    // nó chả động tĩnh gì"*. Bấm CÓ ghi vào sổ — nhưng `CHECK_XN`, `KHAC`,
    // `TRA_KQ`, `HOI_THAM` xưa nay ghi với `appointment_id = NULL` (đo trên
    // staging: 19/40 dòng), mà bản vá "tích xanh theo lượt" ngay trước đó lọc
    // sổ theo `appointment_id`. Nên dòng vừa ghi bị chính màn hình loại ra:
    // ghi thật, tích không lên, người dùng thấy nút chết.
    //
    // Backend chỉ ĐÒI `appointment_id` cho năm loại kia; nó nhận với mọi loại
    // và còn kiểm lịch ấy đúng của khách này. Gắn luôn là vừa sửa được cái nút,
    // vừa gom đúng bước vào đúng lượt ở ô Lịch sử các lần khám.
    setDangGhiLoiRa(v.khoa);
    setLoiGhiLoiRa(null);
    // Khoá theo thao tác — xem khoa-mot-lan.ts.
    const ttLoiRa = dinhDanhThaoTac(clinicPatientId, lich.id, v.loai, v.ketQua, v.khoa);
    const res = await fetch("/api/cskh/tuong-tac", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": khoaThaoTac(ttLoiRa),
      },
      body: JSON.stringify({
        clinic_patient_id: clinicPatientId,
        appointment_id: lich.id ?? null,
        loai: v.loai,
        // BA LUẬT CHÉO của backend gom vào `kenhCho` — gửi sai là 422, và
        // `BO_QUA` (nút "Không cần follow up") là cái từng gửi sai suốt.
        kenh: kenhCho(v.ketQua),
        ket_qua: v.ketQua,
        khach_xac_nhan: v.khachXacNhan ?? null,
        xac_minh_cach: v.xacMinhCach ?? null,
        // GHI CHÚ NGƯỜI DÙNG GÕ THẮNG nội dung mặc định. Mặc định chỉ là câu
        // mô tả việc ("Đã gọi xác nhận lịch"); thứ người trực gõ tay bao giờ
        // cũng nói được nhiều hơn ("khách đang họp, gọi lại sau 5h").
        noi_dung: ghiChu.trim() || v.noiDung.trim() || null,
        trang_thai_ma: ma,
      }),
    });
    setDangGhiLoiRa(null);
    if (res.ok) onGhiChuXong?.();
    if (!res.ok) {
      const d = (await res.json().catch(() => null)) as {
        error?: string;
        message?: string;
      } | null;
      // MÁY CHỦ TỪ CHỐI (4xx) ⇒ BỎ KHOÁ THAO TÁC.
      //
      // 4xx nghĩa là chắc chắn chưa ghi gì, và lần bấm lại sau khi sửa là một
      // thao tác MỚI. Giữ khoá thì lần ấy đâm vào chính hàng đang PROCESSING
      // trong bảng idempotency_key và nhận 409 "Yêu cầu với Idempotency-Key này
      // đang được xử lý" — kẹt đủ 5 phút, và câu giải thích THẬT ("chưa gửi tệp
      // kết quả cho khách") biến mất sau nó.
      //
      // 5xx / lỗi mạng thì GIỮ khoá: lúc đó không ai biết máy chủ đã ghi tới
      // đâu, và bỏ khoá là mở đường cho một bản ghi thứ hai.
      if (res.status >= 400 && res.status < 500) xongThaoTac(ttLoiRa);
      setLoiGhiLoiRa({
        ma: v.khoa,
        cau: nhanLoi(d, `Không ghi được (lỗi ${res.status}).`),
      });
      return;
    }
    xongThaoTac(ttLoiRa); // xong ⇒ lần bấm sau là thao tác mới
    router.refresh();
  }

  /** SỔ CHĂM SÓC CỦA RIÊNG LƯỢT ĐANG XEM.
   *
   *  LỖI QUANG TÌM RA 10/08/2026: khám xong cho Huyền rồi đặt lịch khám mới thì
   *  *"bên phải nó cũng chưa update cho lượt khám mới ấy"* — và cột giữa cũng
   *  vậy. Cả chuỗi trạng thái vẫn xanh nguyên từ lượt trước.
   *
   *  Vì `lichSu` là sổ của cả KHÁCH, không phải của một LƯỢT. `lanCuoi` dò
   *  `trang_thai_ma` trên toàn bộ sổ, nên mọi bước đã làm ở lượt tháng trước
   *  vẫn tích xanh ở lượt hôm nay — lượt mới sinh ra đã "hoàn thành" sẵn, và
   *  người trực không còn gì để làm theo màn hình.
   *
   *  Lọc theo `appointment_id` (cột có từ 20260809000003, vừa được mang xuống
   *  UI).
   *
   *  KHÔNG CÓ LỊCH THÌ SỔ RỖNG, VÀ NÓI RA. Bản 10/08 sáng viết `: lichSu` —
   *  "thà tích thừa còn hơn một màn trắng không giải thích được". Nhưng nó tích
   *  thừa TRONG IM LẶNG, và đúng lúc `lich.id` hay bị null nhất: ngay sau
   *  checkout. Người trực mở một lượt vừa sinh ra đã thấy đủ tám bước xanh —
   *  không còn gì để làm theo màn hình, mà chẳng có gì báo là màn đang nói về
   *  lượt khác. Rỗng KÈM MỘT DÒNG CHỮ thì người đọc biết mình đang thiếu gì. */
  // DÒNG ĐÃ HOÀN TÁC KHÔNG ĐƯỢC TÍNH — nhưng vẫn nằm trong sổ.
  //
  // Quang 10/08/2026 muốn bấm nhầm thì rút lại được, và log thì không được xoá.
  // Nên `huy_luc` là lá cờ: dòng ở lại cho "Lịch sử các lần khám" đọc, còn mọi
  // phép suy trạng thái ở đây bỏ qua nó — đúng như `v_viec_cskh` làm ở server.
  // Hai bên phải cùng luật, nếu không node tích xanh mà chip bên trái mở lại.
  const lichSuLuotNay = (
    lich.id ? lichSu.filter((d) => d.appointment_id === lich.id) : []
  ).filter((d) => !d.huy_luc);
  const khongGanDuocLuot = !lich.id && lichSu.length > 0;

  const [dangHoanTac, setDangHoanTac] = useState<string | null>(null);
  const [loiHoanTac, setLoiHoanTac] = useState<string | null>(null);

  /** CHẠM MỚI NHẤT CỦA KHÁCH nằm NGOÀI lượt đang xem — nút tròn không với tới.
   *
   *  Tuyền 18/08/2026: "có những lúc dù F5 nhưng hệ thống không cho undo sau
   *  khi đã chuyển trạng thái". Đúng, và F5 chính là thủ phạm: mất tham số
   *  `?luot=` là màn tự chọn lượt theo `luotMacDinh`, có thể KHÁC lượt mà lần
   *  chạm vừa ghi vào; node chỉ rút được dòng của lượt đang xem
   *  (`lichSuLuotNay`), nên thao tác vừa làm thành không rút lại được. Dòng
   *  ghi khi khách chưa gắn lượt (`appointment_id` null) thì tệ hơn: không
   *  lượt nào rút được nó.
   *
   *  Vá bằng một lối rút DỰ PHÒNG ở đầu vùng làm việc, CHỈ hiện khi node bất
   *  lực (chạm mới nhất khác lượt / không gắn lượt) — cùng lượt thì nút tròn
   *  vẫn là đường chính, không bày hai nút cho một việc. `CHECK_OUT` không
   *  vào đây: backend từ chối rút mốc đóng lượt có chủ ý (xem `hoan_tac`). */
  const chamMoiNhat = lichSu.find((d) => !d.huy_luc);
  const rutNgoaiLuot =
    chamMoiNhat &&
    // Dòng gộp từ `nhac_tai_kham` không có id — chúng đóng bằng đường khác,
    // không rút từ đây được.
    chamMoiNhat.id &&
    chamMoiNhat.loai !== "CHECK_OUT" &&
    chamMoiNhat.appointment_id !== lich.id
      ? { ...chamMoiNhat, id: chamMoiNhat.id }
      : null;

  /** RÚT LẠI MỘT LẦN CHẠM BẤM NHẦM.
   *
   *  Quang 10/08/2026: *"nhấn vào nút tròn của các sự kiện để hoàn tác… tất
   *  nhiên là log không được xoá, mà là hoàn tác lại tác vụ đó"*.
   *
   *  Backend đặt `huy_luc` trên chính dòng ấy — dòng Ở LẠI, chỉ thôi được tính.
   *  Với `CHECK_IN` nó còn gọi `undo_checkin` để đưa lịch hẹn về CONFIRMED;
   *  `CHECK_OUT` thì từ chối, vì máy trạng thái không có đường ra khỏi
   *  COMPLETED. Xem `TuongTacCskhService.hoan_tac`.
   *
   *  KHÔNG HỎI LẠI (Quang chốt 10/08/2026: *"click vào nút tròn là tự back lại,
   *  không cần xác nhận kiểu vậy"*).
   *
   *  Bản đầu tôi chèn một `window.confirm` vì nút tròn nằm ngay cạnh "Làm lại"
   *  và cả hai đều nhỏ. Nhưng cái giá của một cú rút nhầm THẤP: bấm "Làm bước
   *  này" là ghi lại ngay, và dòng cũ vẫn nằm nguyên trong sổ. Một hộp thoại
   *  chặn đường cho một việc rẻ như thế thì người ta bấm OK theo phản xạ —
   *  tức nó không bảo vệ được gì, chỉ thêm một cú bấm cho MỌI lần dùng đúng.
   *
   *  Hộp thoại xứng đáng ở chỗ mất mát KHÔNG lấy lại được. Đây không phải chỗ
   *  đó — chỗ đó là `CHECK_OUT`, và ở đấy backend từ chối hẳn. */
  async function hoanTac(id: string) {
    setDangHoanTac(id);
    setLoiHoanTac(null);
    const res = await fetch(`/api/cskh/tuong-tac/${id}/hoan-tac`, {
      method: "POST",
    });
    setDangHoanTac(null);
    if (!res.ok) {
      const d = (await res.json().catch(() => null)) as {
        error?: string;
        message?: string;
      } | null;
      setLoiHoanTac(nhanLoi(d, `Không hoàn tác được (lỗi ${res.status}).`));
      return;
    }
    router.refresh();
  }

  const [dangGoiNhac, setDangGoiNhac] = useState<string | null>(null);
  const [loiGoiNhac, setLoiGoiNhac] = useState<string | null>(null);

  /** GHI KẾT QUẢ MỘT CUỘC GỌI NHẮC TÁI KHÁM — và đóng việc ấy.
   *
   *  ĐƯỜNG NÀY VẪN MỞ CHO CSKH SUỐT THỜI GIAN QUA, chỉ là không nút nào gọi
   *  tới. Khối "Nhắc tái khám" bị gỡ khỏi màn 09/08/2026 vì nó trùng với ô
   *  "GỌI NHẮC ĐI KHÁM" ở cột phải — nhưng ô ấy chỉ đổi tiêu đề, không đóng
   *  được `nhac_tai_kham`. Hệ quả: chip "Nhắc đi khám hôm nay · quá giờ hẹn"
   *  đỏ vĩnh viễn ở danh sách, và CSKH không có cách nào tắt.
   *
   *  Đo trên staging 10/08/2026: Bùi Lan Hương và Nguyễn Thị Lan đều đang kẹt
   *  đúng như vậy, cả hai đã quá hạn.
   *
   *  Kết quả BẮT BUỘC, và bốn kết quả khác nhau thật: "chuông đổ không ai bắt"
   *  cũng là một việc đã làm, và nó phải khác "đã nói chuyện được" — không phân
   *  biệt thì hôm sau người khác mở lên thấy "đã gọi" rồi bỏ qua một người chưa
   *  ai nói chuyện với. */
  async function ghiGoiNhac(viecId: string, ketQua: string) {
    setDangGoiNhac(viecId + ketQua);
    setLoiGoiNhac(null);
    const res = await fetch(`/api/recall-jobs/${viecId}/ket-qua`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ket_qua: ketQua, ghi_chu: ghiChu.trim() || null }),
    });
    setDangGoiNhac(null);
    if (!res.ok) {
      const d = (await res.json().catch(() => null)) as {
        error?: string;
        message?: string;
      } | null;
      setLoiGoiNhac(nhanLoi(d, `Không ghi được (lỗi ${res.status}).`));
      return;
    }
    onGhiChuXong?.();
    router.refresh();
  }

  const daHuy = lich.status === "CANCELLED";
  const daCheckin =
    lich.status === "CHECKED_IN" || lich.status === "COMPLETED";

  function cacLan(loai: string): DongLichSu[] {
    // Cũng chỉ trong lượt đang xem — xem ghi chú ở `lichSuLuotNay`. `dangO`
    // đọc hàm này, nên không lọc thì "đang ở đây" cũng kẹt lại ở lượt cũ.
    return lichSuLuotNay.filter((d) => d.loai === loai);
  }

  /** Trạng thái này có ĐANG đúng với khách không — suy từ dữ liệu thật. */
  function dangO(ma: string): boolean {
    if (viecCuaLuot.some((v) => v.trang_thai === ma)) return true;
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
    const theoMa = lichSuLuotNay.find((d) => d.trang_thai_ma === ma);
    if (theoMa) return theoMa;
    const loai = SUY_THEO_LOAI_CU[ma];
    return loai ? lichSuLuotNay.find((d) => loai.includes(d.loai)) : undefined;
  }


  /** Bấm vòng tròn của một ô CSKH: chưa tích → ghi; đã tích → hoàn tác. */
  function bamO(
    lan: DongLichSu | undefined,
    ghi: () => Promise<void> | void,
  ): void {
    if (lan?.id) {
      void hoanTac(lan.id);
      return;
    }
    void ghi();
  }

  /** Dòng GOI_LAI gần nhất của lượt mang một trong các kết quả cho trước.
   *
   *  "Hẹn gọi lại" và "Không gọi được" từng là ba lối ra của MỘT hàng gộp
   *  (`trang_thai_ma = GOI_LAI`). Nay là hai ô riêng, nhưng vẫn ghi cùng mã
   *  trạng thái để view `v_viec_cskh` và sổ cũ đọc như trước — ô phân biệt
   *  theo `ket_qua`. */
  function lanGoiLai(ketQua: string[]): DongLichSu | undefined {
    return lichSuLuotNay.find(
      (d) =>
        (d.trang_thai_ma === "GOI_LAI" || d.trang_thai_ma === "HEN_GOI_LAI") &&
        ketQua.includes(d.ket_qua ?? ""),
    );
  }

  // ── Kết quả xét nghiệm của lượt: đối tác gửi → bác sĩ cho phép → CSKH gửi ──
  const coViec = (ma: string) => viecCuaLuot.some((v) => v.trang_thai === ma);
  // Chỉ tệp XÉT NGHIỆM / đối tác mới bật ô này — tệp siêu âm, thủ thuật thì
  // không (17/09/2026: vừa có video siêu âm đã báo "Bác sĩ đã cho phép gửi").
  const tepXetNghiem = tepCuaLuot.filter((t) => t.la_ket_qua_xet_nghiem !== false);
  // Lượt ĐÃ có tệp trong tay → tin tệp (đã lọc riêng XN). Việc CSKH từ máy chủ
  // (KQ_CHUA_GUI / CHO_BAC_SI) đếm MỌI tệp, kể cả video siêu âm, nên chỉ dùng
  // làm dự phòng khi màn chưa nạp tệp của lượt này.
  const coTep = tepCuaLuot.length > 0;
  const kqChoPhep = coTep
    ? tepXetNghiem.some((t) => t.cho_phep_gui_luc)
    : coViec("KQ_CHUA_GUI");
  const kqDaVe = coTep
    ? tepXetNghiem.length > 0
    : coViec("CHO_BAC_SI") || kqChoPhep;
  const viecDoiTac = lich.doi_tac ?? [];
  const doiTacChuaGui = viecDoiTac.filter((d) => d.trang_thai !== "DA_GUI_KET_QUA");
  const kqChoDoiTac = coViec("CHO_KQ_XN") || doiTacChuaGui.length > 0;
  const cauDoiTac = viecDoiTac
    .map((d) => `${d.ten}: ${NHAN_DOI_TAC[d.trang_thai]}${d.luc ? ` (${ngayGio(new Date(d.luc))})` : ""}`)
    .join(" · ");
  const daTraKq =
    cacLan("TRA_KQ").some((d) => d.ket_qua === "DA_LIEN_HE") ||
    (tepXetNghiem.length > 0 && tepXetNghiem.every((t) => t.gui_luc));

  // ── Thủ thuật + theo dõi sau: bác sĩ quyết ──────────────────────────────────
  const hanTheoDoi =
    lich.theo_doi_thu_thuat === "CAN" &&
    lich.thu_thuat_xong_luc &&
    lich.theo_doi_sau_ngay
      ? new Date(
          new Date(lich.thu_thuat_xong_luc).getTime() +
            lich.theo_doi_sau_ngay * 86_400_000,
        )
      : null;
  const canhBaoTheoDoi = hanTheoDoi
    ? hanTheoDoi.getTime() <= nowMs()
      ? `Quá hạn gọi hỏi thăm sau thủ thuật (hạn ${ngayGio(hanTheoDoi)})`
      : `Gọi hỏi thăm sau thủ thuật trước ${ngayGio(hanTheoDoi)}`
    : null;
  return (
    <div className="min-w-0 space-y-3">
      <section
        aria-label={`Trạng thái khách hàng — ${tenKhach}`}
        className="min-w-0 overflow-hidden rounded-2xl border border-line bg-surface shadow-card"
      >
        {/* TIÊU ĐỀ MỘT DÒNG. Dòng phụ "Bấm vào bước để làm…" đã bỏ theo yêu cầu
            09/08 — nó mô tả mô hình chuỗi bước không còn nữa. */}
        <div className="border-b border-line px-4 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold text-ink">
              Trạng thái khách hàng — {tenKhach}
            </h2>
            {/* Chip trạng thái chuyển từ cột danh sách sang đây (16/09/2026):
                xem `chipTrangThai`. */}
            {chipTrangThai}
          </div>
          {/* LƯỢT ĐANG XEM, NÓI RA BẰNG CHỮ.
              Khách có nhiều lượt thì ba cột phải cùng nói về MỘT lượt, và người
              trực phải đọc được mình đang đứng ở lượt nào — bấm sang lượt khác
              trong ô "Lịch sử các lần khám" bên dưới. */}
          {/* THANH CHỌN LƯỢT — thay dòng "Lượt đang xem" chữ nhỏ và khối
              "Lịch sử các lần khám" dưới đáy (16/09/2026). */}
          {thanhLuot}
          {/* Sổ chăm sóc không gắn được vào lượt nào — nói ra thay vì lặng lẽ
              tích xanh bằng dữ liệu của lượt khác. Xem `lichSuLuotNay`. */}
          {loiHoanTac && (
            <p className="rounded-md bg-danger-bg px-2 py-1 text-label text-danger">
              {loiHoanTac}
            </p>
          )}
          {rutNgoaiLuot && (
            <div className="mt-1 rounded-md bg-warning-bg px-2 py-1.5">
              {/* TÔNG CẢNH BÁO, KHÔNG PHẢI CHỮ MỜ. Bản đầu tôi vẽ nó bằng
                  `text-ink-soft` viền mảnh, đặt ngay dưới dòng "Lượt đang xem"
                  cũng chữ mờ — Tuyền dò cả màn không thấy ("tôi có thấy cái
                  thao tác gần nhất nào đâu"). Một lối thoát hiểm mà người cần
                  nó không nhìn ra thì bằng không. */}
              <p className="text-label font-semibold text-warning">
                ↩ Thao tác gần nhất nằm ở{" "}
                {rutNgoaiLuot.appointment_id
                  ? "một lượt khám khác"
                  : "ngoài mọi lượt khám"}{" "}
                — nút tròn bên dưới không rút được
              </p>
              <p className="mt-1 flex flex-wrap items-center gap-2 text-label text-ink-soft">
                <span className="min-w-0">
                  <span className="font-medium text-ink">
                    {nhanLanChamCuoi(rutNgoaiLuot) ??
                      rutNgoaiLuot.noi_dung ??
                      rutNgoaiLuot.loai}
                  </span>
                  {rutNgoaiLuot.xay_ra_luc
                    ? ` · ${gio(rutNgoaiLuot.xay_ra_luc)}`
                    : null}
                </span>
                <button
                  type="button"
                  onClick={() => void hoanTac(rutNgoaiLuot.id)}
                  disabled={dangHoanTac === rutNgoaiLuot.id}
                  className="rounded-md border border-warning px-2 py-0.5 font-semibold text-warning hover:bg-warning hover:text-white disabled:opacity-50"
                >
                  {dangHoanTac === rutNgoaiLuot.id
                    ? "Đang rút lại…"
                    : "↺ Rút lại thao tác này"}
                </button>
              </p>
            </div>
          )}
          {khongGanDuocLuot && (
            <p className="mt-1 rounded-md bg-warning-bg px-2 py-1 text-label font-medium text-warning">
              Khách có {lichSu.length} thao tác chăm sóc nhưng màn chưa gắn được
              vào lượt khám nào — chọn một lượt ở thanh lượt khám phía trên.
            </p>
          )}
        </div>

        <div className="space-y-3 px-4 py-3">
          {/* TRƯỚC KHÁM — ô CSKH bấm vòng tròn; "Huỷ lịch" tự tích. */}
          <div>
            <span className="text-label font-bold uppercase tracking-wide text-ink-faint">
              Trước khám
            </span>
            <div className="mt-1.5 space-y-1">
              <OBuoc
                ten="Xác nhận lịch trước 7 ngày"
                viec="Gọi khách xác nhận lịch, xong bấm vòng tròn để ghi lại"
                xong={Boolean(lanCuoi("CHO_XAC_NHAN"))}
                dang={dangO("CHO_XAC_NHAN")}
                lan={lanCuoi("CHO_XAC_NHAN")}
                dangGhi={
                  dangGhiLoiRa === "CHO_XAC_NHAN" ||
                  dangHoanTac === lanCuoi("CHO_XAC_NHAN")?.id
                }
                onBam={() =>
                  bamO(lanCuoi("CHO_XAC_NHAN"), () =>
                    ghiMotCham("CHO_XAC_NHAN", {
                      ...MOT_CHAM.CHO_XAC_NHAN!,
                      khoa: "CHO_XAC_NHAN",
                    }),
                  )
                }
                loi={loiGhiLoiRa?.ma === "CHO_XAC_NHAN" ? loiGhiLoiRa.cau : null}
              />
              <div className="grid gap-x-3 sm:grid-cols-2">
                <OBuoc
                  ten="Hẹn gọi lại"
                  viec="Khách hẹn gọi lại sau — chọn ngày giờ ở cột phải"
                  xong={Boolean(lanGoiLai(["HEN_GOI_LAI"]))}
                  dang={dangO("HEN_GOI_LAI")}
                  lan={lanGoiLai(["HEN_GOI_LAI"])}
                  chon={dangChon === "HEN_GOI_LAI"}
                  onChon={() => onLamViec("HEN_GOI_LAI")}
                  dangGhi={
                    dangGhiLoiRa === "HEN_GOI_LAI" ||
                    dangHoanTac === lanGoiLai(["HEN_GOI_LAI"])?.id
                  }
                  onBam={() =>
                    bamO(lanGoiLai(["HEN_GOI_LAI"]), async () => {
                      await ghiMotCham("GOI_LAI", {
                        loai: "NHAC_HEN",
                        ketQua: "HEN_GOI_LAI",
                        noiDung: "Khách hẹn gọi lại",
                        khoa: "HEN_GOI_LAI",
                      });
                      onLamViec("HEN_GOI_LAI");
                    })
                  }
                  loi={loiGhiLoiRa?.ma === "HEN_GOI_LAI" ? loiGhiLoiRa.cau : null}
                />
                <OBuoc
                  ten="Không gọi được"
                  viec="Không nghe máy / không liên lạc được"
                  xong={Boolean(lanGoiLai(["KHONG_LIEN_LAC_DUOC", "CHUA_NGHE_MAY"]))}
                  dang={dangO("GOI_LAI")}
                  lan={lanGoiLai(["KHONG_LIEN_LAC_DUOC", "CHUA_NGHE_MAY"])}
                  dangGhi={
                    dangGhiLoiRa === "KHONG_GOI_DUOC" ||
                    dangHoanTac ===
                      lanGoiLai(["KHONG_LIEN_LAC_DUOC", "CHUA_NGHE_MAY"])?.id
                  }
                  onBam={() =>
                    bamO(lanGoiLai(["KHONG_LIEN_LAC_DUOC", "CHUA_NGHE_MAY"]), () =>
                      ghiMotCham("GOI_LAI", {
                        loai: "NHAC_HEN",
                        ketQua: "KHONG_LIEN_LAC_DUOC",
                        noiDung: "Không gọi được cho khách",
                        khoa: "KHONG_GOI_DUOC",
                      }),
                    )
                  }
                  loi={loiGhiLoiRa?.ma === "KHONG_GOI_DUOC" ? loiGhiLoiRa.cau : null}
                />
              </div>
              <OBuoc
                ten="Huỷ lịch"
                viec="Tự tích khi bấm “Đổi / huỷ lịch hẹn” ở cột phải"
                nguon="nút huỷ lịch"
                xong={daHuy}
                dang={false}
                ghiChuThem={
                  daHuy && (lich.ly_do_huy_ma || lich.cancellation_reason) ? (
                    <p className="mt-1 rounded-control bg-surface-sunken px-2 py-1 text-label leading-snug text-ink-soft">
                      <span className="font-semibold text-ink-muted">Lý do huỷ: </span>
                      {nhanLyDoHuy(lich.ly_do_huy_ma)}
                      {lich.cancellation_reason && (
                        <span className="block italic">“{lich.cancellation_reason}”</span>
                      )}
                      {lich.cancelled_at && (
                        <span className="block font-mono text-ink-muted">
                          huỷ lúc {gio(lich.cancelled_at)}
                        </span>
                      )}
                    </p>
                  ) : null
                }
              />
            </div>
          </div>

          {/* NHẮC TÁI KHÁM + LỜI HẸN GỌI LẠI — việc có hạn, giữ nguyên cách ghi. */}
          {taiKham.length > 0 && (
            <div>
              <span className="text-label font-bold uppercase tracking-wide text-ink-faint">
                Nhắc tái khám
              </span>
              <div className="mt-1.5 space-y-2">
                {taiKham.map((v) => (
                  <MotViecGoiNhac
                    key={v.id}
                    viec={v}
                    dang={dangGoiNhac}
                    loi={loiGoiNhac}
                    onGhi={(kq) => void ghiGoiNhac(v.id, kq)}
                  />
                ))}
              </div>
            </div>
          )}
          {henGoiLai.length > 0 && (
            <div id="hen-goi-lai">
              <span className="text-label font-bold uppercase tracking-wide text-ink-faint">
                Đã hẹn gọi lại
              </span>
              <div className="mt-1.5 space-y-2">
                {henGoiLai.map((h) => (
                  <MotLoiHen
                    key={h.id}
                    hen={h}
                    dangDong={dangDongHen === h.id}
                    loi={loiDongHen === h.id ? loiDongHenChu : null}
                    onDong={() => void dongHen(h.id)}
                  />
                ))}
              </div>
            </div>
          )}

          {/* TẠI QUẦY — việc của LỄ TÂN, chỉ đồng bộ sang (Tuyền 16/09/2026). */}
          <div>
            <span className="text-label font-bold uppercase tracking-wide text-ink-faint">
              Tại quầy
            </span>
            <div className="mt-1.5 space-y-1">
              <div className="grid gap-x-3 sm:grid-cols-2">
                <OBuoc
                  ten="Không đến check-in"
                  viec="Lễ tân đánh dấu khách không đến"
                  nguon="lễ tân"
                  xong={lich.status === "NO_SHOW"}
                  dang={false}
                />
                <OBuoc
                  ten="Đã check-in"
                  viec="Lễ tân check-in khách tại quầy"
                  nguon="lễ tân"
                  xong={daCheckin}
                  dang={lich.status === "CHECKED_IN"}
                />
              </div>
              <OBuoc
                ten="Checkout"
                viec={
                  lich.quay_dong_luc
                    ? `Lễ tân đã đóng lượt lúc ${gio(lich.quay_dong_luc)}`
                    : "Lễ tân đóng lượt khám tại quầy"
                }
                nguon="lễ tân"
                xong={Boolean(lich.quay_dong_luc) || lich.status === "COMPLETED"}
                dang={false}
              />
            </div>
          </div>

          {/* SAU KHÁM — kết quả (đối tác + bác sĩ) và thủ thuật (bác sĩ). */}
          <div>
            <span className="text-label font-bold uppercase tracking-wide text-ink-faint">
              Sau khám
            </span>
            <div className="mt-1.5 space-y-1">
              <OBuoc
                ten="Có kết quả xét nghiệm"
                viec={
                  kqChoPhep
                    ? "Bác sĩ đã cho phép gửi — xem tệp và gửi khách ở cột phải"
                    : kqDaVe
                      ? "Kết quả đã về — chờ bác sĩ xem và cho phép gửi"
                      : kqChoDoiTac
                        ? cauDoiTac || "Đang chờ đơn vị xét nghiệm gửi kết quả"
                        : "Chưa có kết quả nào cho lượt này"
                }
                nguon="đối tác + bác sĩ"
                xong={kqChoPhep}
                dang={kqDaVe || kqChoDoiTac}
                chon={dangChon === "KQ_CHUA_GUI" || dangChon === "CHO_BAC_SI"}
                onChon={
                  kqDaVe
                    ? () => onLamViec(kqChoPhep ? "KQ_CHUA_GUI" : "CHO_BAC_SI")
                    : undefined
                }
              />
              <OBuoc
                ten="Đã trả kết quả"
                viec="Tự tích khi bấm “Đã gửi kết quả cho bệnh nhân” ở cột phải"
                nguon="nút gửi kết quả"
                xong={daTraKq}
                dang={kqChoPhep && !daTraKq}
              />
              <div className="grid gap-x-3 sm:grid-cols-2">
                <OBuoc
                  ten="Đã làm thủ thuật"
                  viec={
                    !lich.co_thu_thuat
                      ? "Lượt này không có chỉ định thủ thuật"
                      : lich.thu_thuat_xong_luc
                        ? `Bác sĩ làm xong lúc ${gio(lich.thu_thuat_xong_luc)}`
                        : "Có chỉ định thủ thuật — bác sĩ chưa làm xong"
                  }
                  nguon="bác sĩ"
                  xong={Boolean(lich.thu_thuat_xong_luc)}
                  dang={Boolean(lich.co_thu_thuat) && !lich.thu_thuat_xong_luc}
                  canhBao={canhBaoTheoDoi}
                />
                <OBuoc
                  ten="Không cần follow-up sau thủ thuật"
                  viec={
                    lich.theo_doi_thu_thuat === "KHONG_CAN"
                      ? "Bác sĩ: không cần theo dõi — không gọi hỏi thăm"
                      : lich.theo_doi_thu_thuat === "CAN"
                        ? `Bác sĩ: cần theo dõi sau ${lich.theo_doi_sau_ngay ?? "?"} ngày`
                        : lich.co_thu_thuat
                          ? "Bác sĩ chưa quyết có theo dõi hay không"
                          : "—"
                  }
                  nguon="bác sĩ"
                  xong={lich.theo_doi_thu_thuat === "KHONG_CAN"}
                  dang={lich.theo_doi_thu_thuat === "CAN"}
                  canhBao={lich.theo_doi_thu_thuat === "CAN" ? canhBaoTheoDoi : null}
                />
              </div>
            </div>
          </div>

          {/* ĐẶT LỊCH TIẾP — KHÔNG đóng lượt nữa. Checkout là việc của lễ tân
              (Tuyền chốt 16/09/2026); hai nút này chỉ mở form đặt lịch. */}
          <div className="space-y-1.5 border-t border-line pt-3 text-center">
            <span className="text-label font-bold uppercase tracking-wide text-ink-faint">
              Đặt lịch tiếp
            </span>
            <div className="flex flex-wrap justify-center gap-1.5">
              <button
                type="button"
                onClick={() => onDatLich?.("tai-kham")}
                disabled={!lich.id}
                title={
                  !lich.id
                    ? "Khách chưa có lượt khám nào để nối tiếp"
                    : `Đặt lịch tái khám nối tiếp lượt đang xem${
                        lich.service_name ? ` — giữ dịch vụ ${lich.service_name}` : ""
                      }`
                }
                className="rounded-control px-2.5 py-1.5 text-label font-medium text-brand-700 ring-1 ring-inset ring-brand-300 hover:bg-brand-50 disabled:opacity-40"
              >
                Tái khám
              </button>
              <button
                type="button"
                onClick={() => onDatLich?.("kham-moi")}
                title="Đặt một lịch mới cho chuyện khác, ngày khác — không nối chuỗi"
                className="rounded-control px-2.5 py-1.5 text-label font-medium text-ink-soft ring-1 ring-inset ring-line hover:bg-surface-muted"
              >
                Đặt lịch khám mới
              </button>
            </div>
          </div>
        </div>

        {/* Khối "KẾT QUẢ SIÊU ÂM / XÉT NGHIỆM" và dòng "Giờ khám" cũng đã bỏ
            (Quang chốt 09/08/2026). `TepKetQua` KHÔNG chết theo — màn
            HanhDongTrangThai vẫn dựng nó ở bước "Đã có kết quả, chưa gửi", đúng
            chỗ người ta thật sự tải kết quả lên. */}

        {/* LỊCH SỬ THAO TÁC CỦA CẢ HỒ SƠ — không phụ thuộc lượt hay trạng thái.
            Khách hỏi (qua Tuyền, 18/08/2026): "cần hiển thị lịch sử thao tác
            trên từng hồ sơ mà không cần chuyển trạng thái". Trước đây các dòng
            sổ chỉ hiện RẢI trong "Lịch sử các lần khám" theo từng lượt — dòng
            không gắn lượt thì không hiện đâu cả. Đây là SỔ ĐỌC nguyên vẹn:
            dòng đã rút lại vẫn nằm đó, gạch ngang (phép KỂ, xem PR 140). */}
        {lichSu.length > 0 && (
          <details className="border-t border-line px-4 py-2.5">
            <summary className="cursor-pointer select-none text-label font-bold uppercase tracking-wide text-ink-faint">
              Lịch sử thao tác ({lichSu.length})
            </summary>
            <ul className="mt-2 space-y-1.5">
              {lichSu.map((d, i) => (
                <li
                  key={d.id ?? `${d.xay_ra_luc}-${i}`}
                  className={`text-label ${
                    d.huy_luc ? "text-ink-faint" : "text-ink-soft"
                  }`}
                >
                  <span className="tabular-nums">{gio(d.xay_ra_luc)}</span>
                  {" · "}
                  <span
                    className={
                      d.huy_luc ? "italic line-through" : "font-medium text-ink"
                    }
                  >
                    {nhanLanChamCuoi(d) ?? d.noi_dung ?? d.loai}
                  </span>
                  {d.ket_qua && NHAN_KET_QUA[d.ket_qua]
                    ? ` — ${NHAN_KET_QUA[d.ket_qua]}`
                    : null}
                  {d.nhan_vien ? ` · ${d.nhan_vien}` : null}
                  {d.huy_luc ? " · đã rút lại" : null}
                  {!d.appointment_id ? " · không gắn lượt" : null}
                </li>
              ))}
            </ul>
          </details>
        )}
      </section>

      {children}
    </div>
  );
}
