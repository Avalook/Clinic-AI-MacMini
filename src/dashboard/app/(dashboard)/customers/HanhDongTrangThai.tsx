"use client";

// HÀNH ĐỘNG ỨNG VỚI TRẠNG THÁI ĐANG CHỌN — khối bên phải màn Quản lý khách hàng.
//
// Đặc tả chị Thu qua Quang (09/08/2026): mỗi trạng thái có một bộ nút RIÊNG,
// không phải bốn nút chung cho mọi trạng thái. Bấm xong thì node bên trái tích
// xanh. Bảng dưới đây là bản dịch trực tiếp của đặc tả ấy, từng dòng một.
//
// MỌI NÚT ĐỀU GHI SỔ. Không nút nào chỉ đổi màu trên màn hình: tất cả đi qua
// POST /api/cskh/tuong-tac → `tuong_tac_cskh` + `event_log`, nên node tích xanh
// vì có một dòng THẬT trong database, không vì một biến trong trình duyệt.
// Đó cũng là lý do tích xanh sống qua F5 và người ca sau nhìn thấy.

import { useState } from "react";
import { nhanLoi } from "@/lib/loi-api";
import { useRouter } from "next/navigation";
import { Phone, Upload, Send, Check, X, CalendarPlus } from "lucide-react";
import { LY_DO_HUY, LY_DO_HUY_THU_TU } from "@/lib/ly-do-huy";
import TepKetQua, { type TepKetQuaRow } from "./TepKetQua";

/** Khối hành động ĐỔI THEO VIỆC ĐANG PHẢI LÀM.
 *
 *  TRƯỚC ĐÂY NÓ ĐỨNG YÊN. Bốn nút — Gọi, Ghi kết quả gọi, Zalo nhắc hẹn, Zalo
 *  báo có KQ — hiện y hệt nhau bất kể khách đang ở bước nào. Hai chỗ sai rõ
 *  nhất, và cả hai đều dẫn người trực làm sai việc:
 *
 *    · Bước "Hỏi đơn vị xét nghiệm" bày ra một nút quay số MÁY KHÁCH HÀNG.
 *      Việc ấy là gọi cho phòng xét nghiệm, không phải gọi cho bệnh nhân — gọi
 *      khách lúc này là gọi để nói "em chưa có kết quả".
 *    · Bước "Nhắc bác sĩ duyệt kết quả" cũng vậy: người cần chạm là bác sĩ.
 *
 *  Ngoài ra ô "Việc gì" luôn mở sẵn ở "Gọi nhắc hẹn" nên mọi cuộc gọi vào sổ
 *  dưới cùng một loại, và cột "Tương tác gần nhất" nói sai về việc vừa làm.
 *
 *  `goiKhach = false` KHÔNG ẩn ô ghi kết quả — việc vẫn phải được ghi lại. Nó
 *  chỉ bỏ cái nút quay số nhầm người.
 */
interface HanhDongViec {
  tieuDe: string;
  /** Loại tương tác mở sẵn khi CSKH bấm "Ghi kết quả". */
  loai: string;
  /** Có quay số cho KHÁCH ở bước này không. */
  goiKhach: boolean;
  /** Mẫu tin Zalo hợp với bước này; null = không có mẫu nào đúng. */
  zalo: "NHAC_HEN" | "TRA_KET_QUA" | null;
  /** Câu nói rõ bước này chạm tới ai — hiện khi không phải gọi khách. */
  nhacNho?: string;
  /** Bước này ghi ở khối khác (Nhắc tái khám), không ghi ở đây. */
  oKhoiKhac?: string;
}

const HANH_DONG: Record<string, HanhDongViec> = {
  CHO_XAC_NHAN: {
    tieuDe: "Gọi xác nhận lịch",
    loai: "XAC_NHAN_LICH",
    goiKhach: true,
    zalo: "NHAC_HEN",
  },
  NHAC_HEN_MAI: {
    tieuDe: "Gọi nhắc hẹn ngày mai",
    loai: "NHAC_HEN",
    goiKhach: true,
    zalo: "NHAC_HEN",
  },
  GOI_LAI: {
    tieuDe: "Gọi lại — lần trước chưa gặp",
    loai: "NHAC_HEN",
    goiKhach: true,
    zalo: "NHAC_HEN",
  },
  HOI_LY_DO_HUY: {
    tieuDe: "Gọi hỏi vì sao huỷ",
    loai: "HOI_LY_DO_HUY",
    goiKhach: true,
    zalo: null,
  },
  HEN_GOI_LAI: {
    tieuDe: "Đã hẹn gọi lại hôm nay",
    loai: "HOI_THAM",
    goiKhach: true,
    zalo: null,
  },
  KQ_CHUA_GUI: {
    tieuDe: "Gọi trả kết quả cho khách",
    loai: "TRA_KQ",
    goiKhach: true,
    zalo: "TRA_KET_QUA",
  },
  CHO_KQ_XN: {
    tieuDe: "Hỏi đơn vị xét nghiệm",
    loai: "CHECK_XN",
    goiKhach: false,
    zalo: null,
    nhacNho:
      "Bước này gọi cho ĐƠN VỊ XÉT NGHIỆM, không phải cho khách. Ghi lại kết quả hỏi được.",
  },
  CHO_BAC_SI: {
    tieuDe: "Nhắc bác sĩ duyệt kết quả",
    loai: "KHAC",
    goiKhach: false,
    zalo: null,
    nhacNho:
      "Kết quả đang chờ BÁC SĨ xem. Nhắc bác sĩ rồi ghi lại — chưa gọi khách ở bước này.",
  },
  MOI_TAI_KHAM: {
    tieuDe: "Gọi mời tái khám",
    loai: "HOI_THAM",
    goiKhach: true,
    zalo: null,
    oKhoiKhac: "Nhắc tái khám",
  },
  NHAC_DI_KHAM: {
    tieuDe: "Gọi nhắc đi khám",
    loai: "HOI_THAM",
    goiKhach: true,
    zalo: null,
    oKhoiKhac: "Nhắc tái khám",
  },
};

// Năm trạng thái BỔ SUNG theo đặc tả chị Thu (09/08/2026). Chúng không có
// trong `v_trang_thai_cskh` vì view chỉ suy được việc CÒN PHẢI LÀM; đây là chỗ
// khách ĐANG ĐỨNG, và CSKH chọn tay ở cột trạng thái bên trái.
const HANH_DONG_THEM: Record<string, HanhDongViec> = {
  DA_CHECKIN: {
    tieuDe: "Đã check-in — xem việc tiếp theo",
    // Chưa biết là trả kết quả hay hẹn tái khám: đó chính là việc CSKH phải
    // quyết sau khi xem tình trạng sau khám. Ghi dưới dạng "việc khác" rồi
    // chuyển sang đúng trạng thái ở cột bên trái.
    loai: "KHAC",
    goiKhach: false,
    zalo: null,
    nhacNho:
      "Xem tình trạng sau khám rồi chọn tiếp: “Chờ kết quả xét nghiệm” nếu còn đợi xét nghiệm, hoặc hẹn ngày tái khám ở khối Nhắc tái khám.",
  },
  DA_TRA_KQ: {
    tieuDe: "Đã trả kết quả — có cần tái khám không",
    loai: "KHAC",
    goiKhach: false,
    zalo: null,
    oKhoiKhac: "Nhắc tái khám",
    nhacNho:
      "Kết quả đã trả. Việc còn lại là quyết có hẹn tái khám hay không — hẹn thì gõ ngày ở khối Nhắc tái khám để hệ thống tự sinh hai mốc gọi.",
  },
  KHONG_FOLLOW_UP: {
    tieuDe: "Không cần follow up sau thủ thuật",
    loai: "KHAC",
    goiKhach: false,
    zalo: null,
    nhacNho:
      "Ghi lại để ca sau KHÔNG gọi vào ngày mai. Không ghi thì người trực kế tiếp không có cách nào biết, và khách bị gọi thừa.",
  },
  SAU_SINH_1_THANG: {
    tieuDe: "Sau sinh 1 tháng — chúc mừng đầy tháng",
    loai: "HOI_THAM",
    goiKhach: true,
    zalo: null,
    nhacNho:
      "Chúc mừng đầy tháng và mời khám lại sau sinh. Hệ thống KHÔNG tự biết ngày sinh thật (chỉ có ngày dự sinh), nên trạng thái này do CSKH chọn.",
  },
  SAU_THU_THUAT_1_NGAY: {
    tieuDe: "Sau thủ thuật 1 ngày — hỏi thăm",
    loai: "HOI_THAM",
    goiKhach: true,
    zalo: null,
    nhacNho:
      "Gọi hỏi thăm tình trạng sau thủ thuật. Trạng thái này do CSKH chọn — dịch vụ thủ thuật đang tắt nên máy không suy ra được.",
  },
};

/** Tiêu đề của khối hành động, theo trạng thái đang chọn.
 *
 *  Xuất ra để `CustomersView` dựng tiêu đề từ CÙNG một bảng với các nút bên
 *  dưới. Hai bảng cho cùng một khái niệm là hai bảng sẽ lệch — và ở đây lệch
 *  nghĩa là tiêu đề nói một việc còn nút làm một việc khác. */
export function tieuDeHanhDong(ma: string | null | undefined): string {
  if (!ma) return MAC_DINH.tieuDe;
  return (HANH_DONG[ma] ?? HANH_DONG_THEM[ma] ?? MAC_DINH).tieuDe;
}

/** MÃ TRẠNG THÁI THẬT SỰ CÓ BỘ NÚT ở khối này.
 *
 *  Xuất ra để `?viec=` trên đường dẫn được KIỂM trước khi dùng. Chuông thông
 *  báo và ba màn khác đều dựng đường dẫn tới `/customers`, và một mã gõ sai
 *  (hoặc một mã cũ còn nằm trong `thong_bao.duong_dan` sinh từ tuần trước) sẽ
 *  mở màn ở một trạng thái không có nút nào. Thà bỏ qua tham số ấy và chạy theo
 *  việc gấp nhất, còn hơn mở ra một khối trống. */
export function coBoNut(ma: string | null | undefined): boolean {
  if (!ma) return false;
  return ma in HANH_DONG || ma in HANH_DONG_THEM;
}

const MAC_DINH: HanhDongViec = {
  tieuDe: "Gọi khách & ghi tương tác",
  loai: "NHAC_HEN",
  goiKhach: true,
  zalo: "NHAC_HEN",
};

/** Lý do huỷ có sẵn — LẤY TỪ DANH MỤC CHUNG, không chép tay nữa.
 *
 *  Ba dòng cũ ở đây là BẢN THỨ TƯ của cùng một danh mục (sau CHECK trong SQL,
 *  `LY_DO_HUY` ở `booking_service.py`, và `lib/ly-do-huy.ts`), và nó đã lệch
 *  sẵn: chữ khác hẳn ba bản kia, lại thiếu `DAT_TRUNG` thêm ngày 10/08. Chép
 *  một danh mục là hẹn ngày mỗi màn nói một kiểu về cùng một lần huỷ — đúng
 *  chuyện đã làm nút "Bỏ lịch này" trả 500 hôm nay.
 *
 *  Bỏ `DAT_TRUNG` khỏi ô này: nó là lý do của người dọn lịch trùng, không phải
 *  câu khách nói qua điện thoại. Ô này ghi lời khách. */
const LY_DO_HUY_SAN: string[] = LY_DO_HUY_THU_TU.filter(
  (ma) => ma !== "DAT_TRUNG" && ma !== "KHAC",
).map((ma) => LY_DO_HUY[ma]!);

interface Props {
  trangThai: string | null;
  clinicPatientId: string;
  patientCode: string;
  appointmentId: string | null;
  phone: string | null;
  tepKetQua: TepKetQuaRow[];
  /** Trạng thái này đã có dấu vết xử lý chưa — để nút nói "làm lại". */
  daXong: boolean;
}

export default function HanhDongTrangThai({
  trangThai,
  clinicPatientId,
  patientCode,
  appointmentId,
  phone,
  tepKetQua,
  daXong,
}: Props) {
  const router = useRouter();
  const [dangLuu, setDangLuu] = useState<string | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [xong, setXong] = useState(false);
  const [ghiChu, setGhiChu] = useState("");
  const [lyDo, setLyDo] = useState("");
  const [moLyDoSan, setMoLyDoSan] = useState(false);
  const [moHen, setMoHen] = useState(false);
  const [ngayHen, setNgayHen] = useState("");
  /** "" = chỉ hẹn tới ngày. Không mặc định 00:00 — xem chú thích ô nhập. */
  const [gioHen, setGioHen] = useState("");
  const [lyDoHen, setLyDoHen] = useState("");
  const [daHen, setDaHen] = useState(false);

  /** Ghi một lần chạm. `loai`/`ket_qua` phải nằm trong bộ từ backend canh
   *  (LOAI_HOP_LE, KET_QUA_HOP_LE ở tuong_tac_cskh_service.py). */
  async function ghi(
    ma: string,
    loai: string,
    ketQua: string,
    noiDung?: string,
  ) {
    // MỐC QUẦY có luật riêng ở backend: kênh phải là TRUC_TIEP và kết quả phải
    // là GHI_NHAN (chúng là việc XẢY RA, không phải cuộc gọi). Gửi sai là 422.
    const mocQuay = ["CHECK_IN", "CHECK_OUT", "THANH_TOAN", "MUA_THUOC"].includes(
      loai,
    );
    setDangLuu(ma);
    setLoi(null);
    try {
      const res = await fetch("/api/cskh/tuong-tac", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          clinic_patient_id: clinicPatientId,
          // LUÔN GẮN LỊCH HẸN KHI CÓ.
          //
          // Chỗ này từng chỉ gắn cho năm loại của `CAN_LICH_HEN` — tập hợp
          // backend BẮT BUỘC phải có lịch — và gửi null cho mọi loại khác. Đúng
          // theo nghĩa "không vi phạm ràng buộc", nhưng nó vứt đi thông tin lượt
          // khám: `CHECK_XN`, `KHAC`, `TRA_KQ`, `HOI_THAM` vào sổ mà không biết
          // thuộc lượt nào.
          //
          // Hệ quả lộ ra ngày 10/08/2026, khi timeline bắt đầu lọc sổ theo lượt:
          // bấm mấy nút ấy thì ghi thật nhưng không tích xanh, vì chính màn hình
          // loại dòng vừa ghi ra. Và ô "Lịch sử các lần khám" cũng không gom
          // được chúng vào đúng lượt.
          //
          // Backend chỉ ĐÒI với năm loại kia; nó NHẬN với mọi loại và tự kiểm
          // lịch hẹn có đúng của khách này không.
          appointment_id: appointmentId,
          loai,
          // "BỎ QUA" LÀ KHÔNG GỌI AI CẢ, nên kênh phải là KHONG_LIEN_HE.
          //
          // Chỗ này từng gửi cứng "GOI" cho mọi thứ không phải mốc quầy, kể cả
          // nút "Ghi nhận: không cần gọi" (ket_qua = BO_QUA). Cả backend lẫn
          // ràng buộc `tuong_tac_bo_qua_thi_khong_lien_he` của database đều đòi
          // BO_QUA ⟺ KHONG_LIEN_HE, nên nút ấy CHƯA TỪNG ghi được lần nào: bấm
          // là hiện dòng đỏ "'Bỏ qua' phải đi cùng 'không liên hệ'", và bước
          // trên timeline không bao giờ tích xanh.
          //
          // Ghi một dòng "đã gọi" cho một việc mà cả ý nghĩa của nó là KHÔNG
          // gọi thì còn tệ hơn: nó vào sổ chăm sóc như một cuộc gọi chưa từng có.
          kenh: mocQuay
            ? "TRUC_TIEP"
            : ketQua === "BO_QUA"
              ? "KHONG_LIEN_HE"
              : "GOI",
          ket_qua: mocQuay ? "GHI_NHAN" : ketQua,
          noi_dung: (noiDung ?? ghiChu).trim() || null,
          // MÃ TRẠNG THÁI mà thao tác này đóng lại. Đây là thứ timeline dò để
          // tích xanh — không dò theo `loai` nữa, vì nhiều trạng thái dùng
          // chung một loại (xem migration 20260810000002).
          trang_thai_ma: trangThai,
        }),
      });
      if (!res.ok) {
        const d = (await res.json().catch(() => null)) as {
          error?: string;
          message?: string;
        } | null;
        setLoi(nhanLoi(d, "Không ghi được."));
        return false;
      }
      setXong(true);
      setGhiChu("");
      router.refresh();
      return true;
    } finally {
      setDangLuu(null);
    }
  }

  /** HẸN GỌI LẠI NGÀY… — chỗ đựng việc hệ thống chưa suy được.
   *
   *  Nó vốn nằm trong khối "Ghi một tương tác khác" đã bỏ. Giữ lại vì đây là
   *  đường DUY NHẤT sinh ra việc `hen_goi_lai`, tức trạng thái "Hẹn gọi lại
   *  sau" trên timeline. Bỏ theo luôn là lặng lẽ gỡ một trạng thái trong đặc
   *  tả của chị Thu. */
  async function henGoiLai() {
    setDangLuu("hen");
    setLoi(null);
    try {
      const res = await fetch("/api/cskh/hen-goi-lai", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          clinic_patient_id: clinicPatientId,
          ngay_goi: ngayHen,
          // Chuỗi rỗng KHÔNG được gửi thành "" — backend khai `time | None`,
          // và "" không parse ra giờ. null nói đúng "chỉ hẹn tới ngày".
          gio_goi: gioHen || null,
          ly_do: lyDoHen.trim(),
        }),
      });
      if (!res.ok) {
        const d = (await res.json().catch(() => null)) as {
          error?: string;
          message?: string;
        } | null;
        setLoi(nhanLoi(d, "Không hẹn được."));
        return;
      }
      router.refresh();
      setDaHen(true);
      setMoHen(false);
      setLyDoHen("");
    } finally {
      setDangLuu(null);
    }
  }

  const soDienThoai = phone ? (
    // "hiện số của khách ở đây luôn" — CSKH không phải quay về cột hồ sơ để
    // đọc số rồi quay lại đây bấm.
    <a
      href={`tel:${phone}`}
      className="block rounded-xl border border-brand-300 bg-white px-3 py-2 text-center font-mono text-sm font-bold text-brand-700 hover:bg-brand-50"
    >
      📞 {phone}
    </a>
  ) : (
    <p className="rounded-xl border border-line bg-surface-muted px-3 py-2 text-center text-xs text-ink-muted">
      Khách chưa có số điện thoại
    </p>
  );

  function NutChinh({
    ma,
    nhan,
    onClick,
    Icon = Check,
  }: {
    ma: string;
    nhan: string;
    onClick: () => void;
    Icon?: typeof Check;
  }) {
    return (
      <button
        type="button"
        onClick={onClick}
        disabled={dangLuu !== null}
        className="inline-flex w-full items-center justify-center gap-1.5 rounded-xl bg-brand-600 py-2 px-3 text-xs font-bold text-white hover:bg-brand-700 disabled:opacity-50"
      >
        <Icon size={14} />
        {dangLuu === ma ? "Đang ghi…" : nhan}
      </button>
    );
  }

  function NutPhu({
    ma,
    nhan,
    onClick,
    Icon,
  }: {
    ma: string;
    nhan: string;
    onClick: () => void;
    Icon?: typeof Check;
  }) {
    return (
      <button
        type="button"
        onClick={onClick}
        disabled={dangLuu !== null}
        className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-xl border border-line bg-surface py-2 px-3 text-xs font-semibold text-ink-soft hover:bg-surface-muted disabled:opacity-50"
      >
        {Icon ? <Icon size={13} /> : null}
        {dangLuu === ma ? "Đang ghi…" : nhan}
      </button>
    );
  }

  const oGhiChu = (
    <input
      value={ghiChu}
      onChange={(e) => setGhiChu(e.target.value)}
      placeholder="Ghi chú (không bắt buộc)"
      className="w-full rounded-lg border border-line bg-surface px-2 py-1.5 text-[11px] text-ink"
    />
  );

  /** `loai` tương tác của trạng thái đang mở, lấy từ CHÍNH bảng sinh ra tiêu
   *  đề. Gõ cứng `loai` trong từng case là cách hai thứ trôi khỏi nhau: tiêu đề
   *  nói "Gọi mời tái khám" mà sổ ghi loại "nhắc hẹn". */
  const loaiCuaTrangThai =
    (trangThai && (HANH_DONG[trangThai] ?? HANH_DONG_THEM[trangThai])?.loai) ||
    "NHAC_HEN";

  function than() {
    switch (trangThai) {
      // ── TRƯỚC KHÁM ────────────────────────────────────────────────────────
      case "CHO_XAC_NHAN":
        return (
          <>
            {soDienThoai}
            {oGhiChu}
            <NutChinh
              ma="xn"
              nhan="Đã gọi xác nhận lịch"
              Icon={Phone}
              onClick={() => void ghi("xn", "XAC_NHAN_LICH", "DA_LIEN_HE")}
            />
          </>
        );

      case "NHAC_HEN_MAI":
        return (
          <>
            {soDienThoai}
            {oGhiChu}
            <NutChinh
              ma="nh"
              nhan="Đã gọi nhắc hẹn"
              Icon={Phone}
              onClick={() => void ghi("nh", "NHAC_HEN", "DA_LIEN_HE")}
            />
          </>
        );

      // ── SAU KHÁM ──────────────────────────────────────────────────────────
      case "DA_CHECKIN":
        return (
          <>
            {/* CHECK-IN PHẢI Ở ĐÂY, và đây là đường DUY NHẤT của màn này.
                `loai = "CHECK_IN"` là thứ gọi BookingService.apply_action
                ("checkin") — nó đổi appointment.status thật, mở lượt khám vào
                hàng đợi tiếp nhận, và làm chip trạng thái bên trái đổi thành
                "Đã check-in" (nhánh DA_CHECKIN của v_trang_thai_cskh,
                migration 20260810000004).

                Nút này TỪNG nằm ở khối "Mốc tại quầy" và bị gỡ cùng khối ấy
                sáng nay — làm màn Quản lý khách hàng mất hẳn khả năng check-in,
                trong khi node "Đã check-in" ngay cạnh chỉ gửi CHECK_OUT. Ghi
                lại để lần sau không ai gỡ nhầm lần nữa.

                Bấm khi khách đã check-in rồi thì không sao: backend thấy status
                đã là CHECKED_IN/COMPLETED là chỉ ghi sổ, không đổi gì. */}
            <NutChinh
              ma="checkin"
              nhan="Check-in cho khách"
              Icon={Check}
              onClick={() =>
                void ghi(
                  "checkin",
                  "CHECK_IN",
                  "GHI_NHAN",
                  "Khách đã tới quầy",
                )
              }
            />
            <p className="text-[11px] leading-snug text-ink-soft">
              Khách đã tới rồi thì chọn việc tiếp theo.
            </p>
            <div className="flex gap-2">
              <NutPhu
                ma="trakq"
                nhan="Trả kết quả xét nghiệm"
                onClick={() =>
                  void ghi(
                    "trakq",
                    // CHECK_OUT chứ không phải KHAC: nó đi qua đúng máy trạng
                    // thái (BookingService.apply_action "complete") nên lịch
                    // hẹn chuyển sang COMPLETED — khách này ĐÃ KHÁM. Ghi
                    // "KHAC" thì mọi màn khác vẫn đọc họ là chưa khám xong.
                    "CHECK_OUT",
                    "GHI_NHAN",
                    "Sau khám: đi hướng trả kết quả xét nghiệm",
                  )
                }
              />
              <NutPhu
                ma="taikham"
                nhan="Đặt lịch tái khám"
                Icon={CalendarPlus}
                onClick={async () => {
                  const ok = await ghi(
                    "taikham",
                    "CHECK_OUT",
                    "GHI_NHAN",
                    "Sau khám: đi hướng đặt lịch tái khám",
                  );
                  if (ok) {
                    router.push(
                      `/appointments?bn=${encodeURIComponent(patientCode)}`,
                    );
                  }
                }}
              />
            </div>
          </>
        );

      case "CHO_KQ_XN":
        return (
          <>
            <p className="text-[11px] font-semibold leading-snug text-ink">
              Check với đơn vị xét nghiệm: đã có kết quả hay chưa?
            </p>
            {oGhiChu}
            <div className="flex gap-2">
              <NutPhu
                ma="co"
                nhan="Có rồi"
                Icon={Check}
                onClick={() =>
                  void ghi(
                    "co",
                    "CHECK_XN",
                    "DA_LIEN_HE",
                    ghiChu.trim() || "Đơn vị XN báo ĐÃ có kết quả",
                  )
                }
              />
              <NutPhu
                ma="chua"
                nhan="Chưa có"
                Icon={X}
                onClick={() =>
                  void ghi(
                    "chua",
                    "CHECK_XN",
                    "DA_LIEN_HE",
                    ghiChu.trim() || "Đơn vị XN báo CHƯA có kết quả",
                  )
                }
              />
            </div>
            <p className="text-[11px] leading-snug text-ink-faint">
              Cả hai đều ghi lại kèm thời điểm — “chưa có” cũng là một lần đã
              hỏi, và ca sau cần biết đã hỏi lúc nào.
            </p>
          </>
        );

      // BA MÃ NÀY VIEW SINH RA NHƯNG `than()` KHÔNG CÓ CASE — tới 10/08/2026
      // chúng rơi thẳng vào `default:` ("Chọn một trạng thái ở cột giữa…"),
      // trong khi `HANH_DONG` vẫn cho chúng một tiêu đề đàng hoàng. Tiêu đề nói
      // "Đã hẹn gọi lại hôm nay", thân màn không có một cái nút nào.
      //
      //   HEN_GOI_LAI  — CSKH tự hẹn với mình, tới ngày thì gọi
      //   MOI_TAI_KHAM — lượt gọi 1 của `nhac_tai_kham`
      //   NHAC_DI_KHAM — lượt gọi 2
      //
      // Cả ba đều là "gọi khách rồi ghi kết quả", đúng bộ nút của `GOI_LAI`.
      // `loai` lấy từ chính `HANH_DONG` để hai bảng không nói hai kiểu.
      case "HEN_GOI_LAI":
      case "MOI_TAI_KHAM":
      case "NHAC_DI_KHAM":
      case "GOI_LAI":
        // BA KẾT QUẢ NÀY TRƯỚC ĐÂY KHÔNG GHI ĐƯỢC TỪ MÀN NÀY.
        //
        // `CHUA_NGHE_MAY`, `KHONG_LIEN_LAC_DUOC`, `HEN_GOI_LAI` có trong bộ từ
        // của backend từ lâu, và chính cái node trên timeline mang tên "KNM /
        // KLLD / Hẹn GLS" — nhưng mọi nút ở đây chỉ gửi `DA_LIEN_HE`, nên sổ
        // chăm sóc ghi "đã liên hệ được" cho cả những lần khách không bắt máy.
        //
        // Hàng gộp bên cột giữa ghi thẳng ba kết quả này chỉ bằng một cú bấm.
        // Ở ĐÂY GIỮ LẠI CHÚNG vì đây là chỗ DUY NHẤT có ô ghi chú: "khách nói
        // đang họp, gọi lại sau 5h" là thứ chỉ ghi được từ khối này.
        return (
          <>
            <p className="text-[11px] leading-snug text-ink-soft">
              Gọi xong thì bấm đúng chuyện đã xảy ra. Cần ghi thêm nội dung thì
              gõ vào ô dưới trước khi bấm.
            </p>
            {soDienThoai}
            {oGhiChu}
            <NutChinh
              ma="gl"
              nhan="Đã liên hệ được"
              Icon={Phone}
              onClick={() => void ghi("gl", loaiCuaTrangThai, "DA_LIEN_HE")}
            />
            <div className="flex flex-wrap gap-2">
              <NutPhu
                ma="knm"
                nhan="Không nghe máy"
                onClick={() => void ghi("knm", loaiCuaTrangThai, "CHUA_NGHE_MAY")}
              />
              <NutPhu
                ma="klld"
                nhan="Không liên lạc được"
                onClick={() =>
                  void ghi("klld", loaiCuaTrangThai, "KHONG_LIEN_LAC_DUOC")
                }
              />
              <NutPhu
                ma="hgl"
                nhan="Hẹn gọi lại sau"
                onClick={() => void ghi("hgl", loaiCuaTrangThai, "HEN_GOI_LAI")}
              />
            </div>
          </>
        );

      case "CHO_BAC_SI":
      case "KQ_CHUA_GUI":
        return (
          <>
            <div className="rounded-xl border border-line bg-surface-muted/60 p-2">
              <div className="mb-1 flex items-center gap-1.5 text-[11px] font-bold text-ink">
                <Upload size={13} /> Kết quả siêu âm / xét nghiệm
              </div>
              <TepKetQua
                clinicPatientId={clinicPatientId}
                appointmentId={appointmentId}
                items={tepKetQua}
              />
            </div>

            {trangThai === "CHO_BAC_SI" ? (
              <>
                <p className="text-[11px] leading-snug text-warning">
                  Kết quả đang chờ BÁC SĨ duyệt. Hỏi bác sĩ trước, chưa gọi
                  khách ở bước này.
                </p>
                {oGhiChu}
                <NutChinh
                  ma="bs"
                  nhan="Đã hỏi bác sĩ"
                  onClick={() =>
                    void ghi(
                      "bs",
                      "KHAC",
                      "DA_LIEN_HE",
                      ghiChu.trim() || "Đã hỏi bác sĩ về kết quả",
                    )
                  }
                />
              </>
            ) : (
              <>
                {oGhiChu}
                <NutChinh
                  ma="gui"
                  nhan="Đã gửi kết quả cho bệnh nhân"
                  Icon={Send}
                  onClick={() =>
                    void ghi(
                      "gui",
                      "TRA_KQ",
                      "DA_LIEN_HE",
                      ghiChu.trim() || "Đã gửi kết quả cho bệnh nhân",
                    )
                  }
                />
                {/* NÓI THẬT VỀ THỨ CHƯA XÂY. Tải lên đã chạy được; GỬI TỰ ĐỘNG
                    thì chưa: Zalo ZNS chỉ gửi được template CHỮ đã duyệt, không
                    đính kèm được tệp hay video. Nên nút trên ghi nhận rằng CSKH
                    đã gửi (qua Zalo cá nhân/Messenger), chứ hệ thống không tự
                    gửi. Nhập nhèm chỗ này là để người trực tin rằng khách đã
                    nhận video trong khi chưa ai gửi. */}
                <p className="rounded-lg border border-dashed border-line px-2 py-1.5 text-[11px] leading-snug text-ink-muted">
                  <b>Đang xây dựng:</b> hệ thống chưa TỰ gửi được ảnh/video cho
                  khách — Zalo ZNS chỉ gửi template chữ. Hiện CSKH gửi bằng kênh
                  của mình rồi bấm nút trên để ghi nhận.
                </p>
              </>
            )}
          </>
        );

      case "DA_TRA_KQ":
        return (
          <>
            {/* HAI NÚT NÀY TỪNG GHI `loai = "KHAC"`, VÀ ĐÓ LÀ LỖI.
                `dangO("DA_TRA_KQ")` ở VungLamViecKhach dò đúng một thứ: có
                tương tác `loai='TRA_KQ'` với `ket_qua='DA_LIEN_HE'` hay không.
                Ghi "KHAC" nên bấm xong node vẫn không sáng lên "đang ở đây" —
                nó chỉ tích xanh nhờ `trang_thai_ma`, tức là đúng một nửa.
                Nhánh KQ_CHUA_GUI của view cũng đóng theo `loai='TRA_KQ'`, nên
                ghi sai loại còn để trạng thái "đã có kết quả, chưa gửi" treo
                lại dù kết quả đã trả xong. */}
            <p className="text-[11px] leading-snug text-ink-soft">
              Kết quả đã trả. Còn một việc: có hẹn tái khám hay không.
            </p>
            <div className="flex gap-2">
              <NutPhu
                ma="cotk"
                nhan="Cần tái khám"
                Icon={CalendarPlus}
                onClick={() =>
                  void ghi(
                    "cotk",
                    "TRA_KQ",
                    "DA_LIEN_HE",
                    "Sau trả kết quả: CẦN hẹn tái khám",
                  )
                }
              />
              <NutPhu
                ma="khongtk"
                nhan="Không cần tái khám"
                Icon={X}
                onClick={() =>
                  void ghi(
                    "khongtk",
                    "TRA_KQ",
                    "DA_LIEN_HE",
                    "Sau trả kết quả: KHÔNG cần tái khám",
                  )
                }
              />
            </div>
            <p className="text-[11px] leading-snug text-ink-faint">
              Chọn “cần tái khám” xong thì gõ ngày ở khối <b>Nhắc tái khám</b>{" "}
              để hệ thống tự sinh hai mốc gọi.
            </p>
          </>
        );

      case "HOI_LY_DO_HUY":
        return (
          <>
            <p className="text-[11px] leading-snug text-ink-soft">
              Gọi lại hỏi lý do huỷ (trong vòng 1–14 ngày kể từ lúc huỷ).
            </p>
            {soDienThoai}
            <div className="space-y-1">
              <textarea
                rows={2}
                value={lyDo}
                onChange={(e) => setLyDo(e.target.value)}
                placeholder="Lý do khách huỷ lịch…"
                className="w-full rounded-lg border border-line bg-surface px-2 py-1.5 text-[11px] text-ink"
              />
              {/* Ô ĐIỀN + TOGGLE BA LÝ DO SẴN, đúng hình dạng đặc tả: người gõ
                  được câu riêng, mà ba trường hợp hay gặp thì bấm một cái là
                  xong — và ba câu ấy giống nhau giữa mọi người, nên về sau đếm
                  được. */}
              <button
                type="button"
                onClick={() => setMoLyDoSan((v) => !v)}
                aria-expanded={moLyDoSan}
                className="text-[11px] font-semibold text-brand-700 hover:underline"
              >
                {moLyDoSan ? "▾ Ẩn lý do có sẵn" : "▸ Chọn lý do có sẵn"}
              </button>
              {moLyDoSan && (
                <ul className="space-y-1">
                  {LY_DO_HUY_SAN.map((l) => (
                    <li key={l}>
                      <button
                        type="button"
                        onClick={() => {
                          setLyDo(l);
                          setMoLyDoSan(false);
                        }}
                        className="w-full rounded-lg border border-line bg-surface px-2 py-1.5 text-left text-[11px] leading-snug text-ink-soft hover:border-brand-400 hover:bg-brand-50"
                      >
                        {l}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <NutChinh
              ma="huy"
              nhan="Ghi lý do huỷ"
              onClick={() =>
                void ghi("huy", "HOI_LY_DO_HUY", "DA_LIEN_HE", lyDo)
              }
            />
          </>
        );

      case "KHONG_FOLLOW_UP":
        return (
          <>
            <p className="text-[11px] leading-snug text-ink-soft">
              Không cần gọi vào ngày hôm sau. Ghi lại để ca sau khỏi gọi thừa.
            </p>
            {oGhiChu}
            <NutChinh
              ma="kfu"
              nhan="Ghi nhận: không cần gọi"
              onClick={() =>
                void ghi(
                  "kfu",
                  "KHAC",
                  "BO_QUA",
                  ghiChu.trim() || "Không cần follow up sau thủ thuật",
                )
              }
            />
          </>
        );

      case "SAU_SINH_1_THANG":
        return (
          <>
            <p className="text-[11px] leading-snug text-ink-soft">
              Chúc mừng đầy tháng, mời khám lại sau sinh.
            </p>
            {soDienThoai}
            {oGhiChu}
            <NutChinh
              ma="ss"
              nhan="Đã gọi chúc mừng đầy tháng"
              Icon={Phone}
              onClick={() => void ghi("ss", "HOI_THAM", "DA_LIEN_HE")}
            />
          </>
        );

      case "SAU_THU_THUAT_1_NGAY":
        return (
          <>
            <p className="text-[11px] leading-snug text-ink-soft">
              Gọi hỏi thăm tình trạng sau thủ thuật.
            </p>
            {soDienThoai}
            {oGhiChu}
            <NutChinh
              ma="stt"
              nhan="Đã gọi hỏi thăm"
              Icon={Phone}
              onClick={() => void ghi("stt", "HOI_THAM", "DA_LIEN_HE")}
            />
          </>
        );

      default:
        // MÃ LẠ PHẢI NÓI RA TÊN NÓ.
        //
        // `trangThai` là chữ tự do đi từ `v_trang_thai_cskh` (và từ `?viec=`
        // trên đường dẫn). Khi một mã có ở view mà chưa có case ở đây, màn hiện
        // câu "Chọn một trạng thái ở cột giữa" — nghe như người dùng chưa bấm
        // gì, trong khi họ vừa bấm xong. Đó là cách ba mã HEN_GOI_LAI /
        // MOI_TAI_KHAM / NHAC_DI_KHAM nằm chết ở đây suốt mà không ai báo lỗi.
        return trangThai ? (
          <p className="text-[11px] leading-snug text-warning">
            Chưa có bộ nút cho trạng thái <b>{trangThai}</b>. Ghi lại mã này rồi
            báo — không phải lỗi thao tác của bạn.
          </p>
        ) : (
          <p className="text-[11px] leading-snug text-ink-muted">
            Chọn một trạng thái ở cột giữa để thấy việc phải làm và các nút
            tương ứng.
          </p>
        );
    }
  }

  return (
    <div className="space-y-2">
      {(xong || daXong) && (
        <p className="flex items-center gap-1.5 rounded-lg bg-success-bg px-2 py-1.5 text-[11px] font-semibold text-success">
          <Check size={13} /> Đã ghi nhận — trạng thái này đã tích xanh ở cột
          giữa. Bấm lại nếu cần làm thêm lần nữa.
        </p>
      )}
      {than()}
      {loi && <p className="text-[11px] text-danger">{loi}</p>}

      {/* Hẹn gọi lại — luôn có, không phụ thuộc trạng thái đang chọn. */}
      <div className="border-t border-line pt-2">
        {daHen ? (
          <p className="rounded-lg bg-success-bg px-2 py-1.5 text-[11px] text-success">
            Đã hẹn gọi lại. Khách hiện ở danh sách vào đúng ngày đó, và lời hẹn
            nằm sẵn trong chuông thông báo tới khi có người xử lý.
          </p>
        ) : moHen ? (
          <div className="space-y-1.5">
            {/* NGÀY VÀ GIỜ, không chỉ ngày (Quang 10/08/2026: *"khách nói đang
                họp, gọi lại sau 5h… thêm 1 nút là gọi lại vào lúc ... giờ"*).
                Với một lời hẹn như thế thì cả-ngày-hôm-nay là câu trả lời sai:
                gọi lúc 9h sáng vẫn đúng "ngày", và vẫn làm phiền đúng người
                mình vừa hứa sẽ không làm phiền.

                Giờ để TRỐNG được — nghĩa là chỉ hẹn tới ngày. Ép chọn giờ thì
                người ta gõ bừa một con số, và con số bừa đó đi thẳng vào việc
                của ca sau. */}
            <div className="flex gap-1.5">
              <input
                type="date"
                value={ngayHen}
                onChange={(e) => setNgayHen(e.target.value)}
                aria-label="Ngày gọi lại"
                className="min-w-0 flex-1 rounded-lg border border-line bg-surface px-2 py-1.5 text-[11px] text-ink"
              />
              <input
                type="time"
                value={gioHen}
                onChange={(e) => setGioHen(e.target.value)}
                aria-label="Giờ gọi lại (bỏ trống nếu chỉ hẹn ngày)"
                title="Bỏ trống nếu chỉ hẹn tới ngày"
                className="w-[92px] shrink-0 rounded-lg border border-line bg-surface px-2 py-1.5 text-[11px] text-ink"
              />
            </div>
            <input
              value={lyDoHen}
              onChange={(e) => setLyDoHen(e.target.value)}
              placeholder="Gọi lại để làm gì"
              className="w-full rounded-lg border border-line bg-surface px-2 py-1.5 text-[11px] text-ink"
            />
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => void henGoiLai()}
                disabled={dangLuu !== null || !ngayHen || !lyDoHen.trim()}
                className="flex-1 rounded-lg bg-brand-600 py-1.5 text-[11px] font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
              >
                {dangLuu === "hen" ? "Đang hẹn…" : "Hẹn"}
              </button>
              <button
                type="button"
                onClick={() => setMoHen(false)}
                className="rounded-lg border border-line px-3 py-1.5 text-[11px] font-medium text-ink-soft hover:bg-surface-muted"
              >
                Thôi
              </button>
            </div>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setMoHen(true)}
            className="w-full rounded-lg border border-line py-1.5 text-[11px] font-semibold text-ink-soft hover:bg-surface-muted"
          >
            Hẹn gọi lại ngày…
          </button>
        )}
      </div>
    </div>
  );
}
